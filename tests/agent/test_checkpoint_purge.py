"""purge_old_checkpoints: no-op cases, plus the real SQL against Postgres.

The Postgres test runs when TEST_DATABASE_URL is set (CI starts a Postgres
service). It uses LangGraph's own saver to write rows, so a schema change in
langgraph-checkpoint-postgres fails here instead of silently in production.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.checkpoint_purge import purge_old_checkpoints


async def test_noop_without_postgres() -> None:
    with patch("src.agent.checkpoint_purge._state", {"postgres_pool": None}):
        assert await purge_old_checkpoints(retention_days=30) == 0


async def test_noop_when_disabled() -> None:
    pool = MagicMock()
    with patch("src.agent.checkpoint_purge._state", {"postgres_pool": pool}):
        assert await purge_old_checkpoints(retention_days=0) == 0
    pool.connection.assert_not_called()


async def test_database_errors_are_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("down"))
    with patch("src.agent.checkpoint_purge._state", {"postgres_pool": pool}):
        assert await purge_old_checkpoints(retention_days=30) == 0
    assert "Checkpoint purge failed" in caplog.text


def test_default_retention_is_30_days() -> None:
    from src.config import Settings

    assert Settings(OPENROUTER_API_KEY="x", SECRET_KEY="x").CHECKPOINT_RETENTION_DAYS == 30


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL")
async def test_deletes_only_idle_threads_whole() -> None:
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    tables = ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "conversation_threads")
    async with AsyncConnectionPool(
        os.environ["TEST_DATABASE_URL"],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        saver = AsyncPostgresSaver(conn=pool)  # type: ignore[arg-type]
        await saver.setup()
        async with pool.connection() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS conversation_threads (thread_id TEXT)")
            for table in tables:
                await conn.execute(f"DELETE FROM {table}")

        async def write(thread_id: str) -> None:
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"messages": ["hola"]}  # stored as a blob
            checkpoint["channel_versions"] = {"messages": "1"}
            saved = await saver.aput(config, checkpoint, {}, {"messages": "1"})
            await saver.aput_writes(saved, [("messages", "bien")], task_id="t1")
            async with pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO conversation_threads (thread_id) VALUES (%s)", (thread_id,)
                )

        for thread_id in ("user:a:old", "user:a:active", "user:a:active"):
            await write(thread_id)
        async with pool.connection() as conn:
            # The old thread's last message was 40 days ago. The active thread
            # has one 40-day-old checkpoint too, but its newest is fresh.
            await conn.execute(
                "UPDATE checkpoints SET checkpoint = jsonb_set(checkpoint, '{ts}',"
                " to_jsonb((NOW() - INTERVAL '40 days')::text)) WHERE thread_id = 'user:a:old'"
                " OR checkpoint_id = (SELECT MIN(checkpoint_id) FROM checkpoints"
                " WHERE thread_id = 'user:a:active')"
            )

        with patch("src.agent.checkpoint_purge._state", {"postgres_pool": pool}):
            assert await purge_old_checkpoints(retention_days=30) == 1

        async with pool.connection() as conn:
            for table in tables:
                cur = await conn.execute(f"SELECT DISTINCT thread_id FROM {table}")
                assert [r["thread_id"] for r in await cur.fetchall()] == ["user:a:active"], table
            cur = await conn.execute("SELECT COUNT(*) AS n FROM checkpoints")
            assert (await cur.fetchone())["n"] == 2  # the active thread keeps its old checkpoint
