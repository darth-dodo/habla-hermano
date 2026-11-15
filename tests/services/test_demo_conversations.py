"""Seeded demo conversations load back through the app's own reader."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.db.encryption import decrypt_field
from src.services.demo_conversations import CONVERSATIONS, seed_conversations
from src.services.thread_messages import get_thread_messages


def test_ten_threads_cover_every_language_and_level() -> None:
    assert len(CONVERSATIONS) == 10
    assert {c[0] for c in CONVERSATIONS} == {"es", "de", "fr", "hi"}
    assert {c[1] for c in CONVERSATIONS if c[0] == "es"} == {"A0", "A1", "A2", "B1"}
    for language in ("de", "fr", "hi"):
        assert (
            len({c[1] for c in CONVERSATIONS if c[0] == language}) == 2
        )  # a low and a higher level


async def test_conversations_round_trip_through_checkpoints() -> None:
    admin = MagicMock()
    count = await seed_conversations(admin, "demo-user", datetime.now(UTC))

    assert count == 10
    admin.table.return_value.delete.return_value.eq.assert_called_with("user_id", "demo-user")
    rows = admin.table.return_value.insert.call_args.args[0]
    assert len({r["thread_id"] for r in rows}) == 10
    for row, (language, level, title, _, turns) in zip(rows, CONVERSATIONS, strict=True):
        assert row["thread_id"].startswith("user:demo-user:")
        assert (row["language"], row["level"]) == (language, level)
        assert row["title"] != title and decrypt_field(row["title"]) == title
        messages = await get_thread_messages(row["thread_id"])
        expected = [m for pair in turns for m in pair]
        assert [m["content"] for m in messages] == expected
        assert [m["role"] for m in messages] == ["human", "ai"] * len(turns)
