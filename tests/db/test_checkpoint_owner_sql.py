"""checkpoint_owner() and the checkpoint RLS policies, on a real Postgres.

Runs when TEST_DATABASE_URL is set (CI has a Postgres service). Applies the
real migrations 004 and 007 to a fresh database per test, with a stub
auth.uid(), and acts as a signed-in user.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL"
)

ME = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
GUEST = "9b2f0c5e-0000-4000-8000-000000000000"  # guest thread_id: a bare session UUID
MIGRATIONS = Path(__file__).parents[2] / "migrations"


@pytest.fixture
def conn():  # type: ignore[no-untyped-def]
    import uuid

    import psycopg
    from psycopg.conninfo import make_conninfo

    base = os.environ["TEST_DATABASE_URL"]
    name = f"rls_{uuid.uuid4().hex[:12]}"  # own database: tests run in parallel workers
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
        for role in ("authenticated", "anon", "service_role"):  # roles are cluster-wide
            admin.execute(
                f"DO $$ BEGIN CREATE ROLE {role}; "
                "EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$"
            )
    try:
        with psycopg.connect(make_conninfo(base, dbname=name), autocommit=True) as conn:
            conn.execute("CREATE SCHEMA auth")
            conn.execute(
                f"CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT '{ME}'::uuid $$"
            )
            conn.execute("GRANT USAGE ON SCHEMA auth TO authenticated")
            for table in (
                "checkpoints",
                "checkpoint_blobs",
                "checkpoint_writes",
                "checkpoint_migrations",
            ):
                conn.execute(f"CREATE TABLE {table} (thread_id TEXT)")
                conn.execute(f"GRANT ALL ON {table} TO authenticated")
            conn.execute((MIGRATIONS / "004_checkpoint_rls.sql").read_text())
            conn.execute((MIGRATIONS / "007_checkpoint_owner_guest_safe.sql").read_text())
            conn.execute(
                "INSERT INTO checkpoints (thread_id) VALUES (%s), (%s), (%s), (%s)",
                (f"user:{ME}:a", f"lesson:{ME}:es-A0-greetings:x", GUEST, f"user:{OTHER}:b"),
            )
            yield conn
    finally:
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {name}")


def test_owner_of_each_thread_id_format(conn) -> None:  # type: ignore[no-untyped-def]
    rows = conn.execute(
        "SELECT checkpoint_owner(%s)::text, checkpoint_owner(%s)::text, checkpoint_owner(%s)",
        (f"user:{ME}:v2", f"lesson:{ME}:es-A0:x", GUEST),
    ).fetchone()
    assert rows == (ME, ME, None)


def test_signed_in_user_sees_and_deletes_only_own_rows_with_guests_present(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute("SET ROLE authenticated")
    visible = [r[0] for r in conn.execute("SELECT thread_id FROM checkpoints ORDER BY 1")]
    assert visible == [f"lesson:{ME}:es-A0-greetings:x", f"user:{ME}:a"]
    # The "Delete all conversations" filter: failed with a guest row before 007.
    deleted = conn.execute(
        "DELETE FROM checkpoints WHERE thread_id LIKE %s RETURNING thread_id", (f"user:{ME}:%",)
    ).fetchall()
    assert deleted == [(f"user:{ME}:a",)]
    conn.execute("RESET ROLE")
    left = [r[0] for r in conn.execute("SELECT thread_id FROM checkpoints ORDER BY 1")]
    assert left == [GUEST, f"lesson:{ME}:es-A0-greetings:x", f"user:{OTHER}:b"]
