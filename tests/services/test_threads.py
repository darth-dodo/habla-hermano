"""Tests for thread management service.

Verifies CRUD operations for conversation thread metadata
with mocked Supabase client. No database connection required.
"""

import re
from datetime import UTC, datetime
from unittest.mock import MagicMock, PropertyMock

from src.db.models import ConversationThread
from src.services.threads import ThreadService

USER_ID = "test-user-abc-123"


def _make_mock_client(data: list[dict] | None = None) -> tuple[MagicMock, MagicMock]:
    """Create a mock Supabase client with chained PostgREST methods.

    Returns (mock_client, mock_table) so tests can override execute().data.
    """
    mock_client = MagicMock()
    mock_table = MagicMock()

    for method in (
        "select",
        "insert",
        "update",
        "delete",
        "eq",
        "order",
    ):
        setattr(mock_table, method, MagicMock(return_value=mock_table))

    mock_execute_result = MagicMock(data=data if data is not None else [])
    mock_table.execute = MagicMock(return_value=mock_execute_result)
    type(mock_table).not_ = PropertyMock(return_value=mock_table)
    mock_client.table = MagicMock(return_value=mock_table)

    return mock_client, mock_table


def _thread_row(
    thread_id: str = f"user:{USER_ID}:aaaa-bbbb",
    title: str = "New conversation",
    language: str = "es",
    level: str = "A1",
) -> dict:
    """Build a dict mimicking a Supabase row for conversation_threads."""
    now = datetime.now(UTC).isoformat()
    return {
        "id": "row-uuid-1",
        "user_id": USER_ID,
        "thread_id": thread_id,
        "title": title,
        "language": language,
        "level": level,
        "created_at": now,
        "updated_at": now,
    }


# =============================================================================
# Create
# =============================================================================


class TestCreateThread:
    """Tests for ThreadService.create_thread."""

    def test_create_thread_returns_conversation_thread(self) -> None:
        """create_thread returns a ConversationThread with correct fields."""
        row = _thread_row()
        mock_client, mock_table = _make_mock_client([row])

        svc = ThreadService(USER_ID, mock_client)
        result = svc.create_thread(language="es", level="A1")

        assert isinstance(result, ConversationThread)
        assert result.user_id == USER_ID
        assert result.language == "es"
        assert result.level == "A1"
        mock_client.table.assert_called_with("conversation_threads")
        mock_table.insert.assert_called_once()

    def test_create_thread_generates_thread_id(self) -> None:
        """thread_id inserted matches format user:{uid}:{uuid4}."""
        row = _thread_row()
        mock_client, mock_table = _make_mock_client([row])

        svc = ThreadService(USER_ID, mock_client)
        svc.create_thread()

        insert_call = mock_table.insert.call_args
        inserted_data = insert_call[0][0]
        pattern = rf"^user:{re.escape(USER_ID)}:[0-9a-f-]{{36}}$"
        assert re.match(pattern, inserted_data["thread_id"]), (
            f"thread_id {inserted_data['thread_id']!r} does not match expected format"
        )

    def test_create_thread_default_language_and_level(self) -> None:
        """Defaults are language='es' and level='A1'."""
        row = _thread_row()
        mock_client, mock_table = _make_mock_client([row])

        svc = ThreadService(USER_ID, mock_client)
        svc.create_thread()

        inserted_data = mock_table.insert.call_args[0][0]
        assert inserted_data["language"] == "es"
        assert inserted_data["level"] == "A1"


# =============================================================================
# List
# =============================================================================


class TestListThreads:
    """Tests for ThreadService.list_threads."""

    def test_list_threads_empty(self) -> None:
        """Returns empty list when user has no threads."""
        mock_client, _ = _make_mock_client([])

        svc = ThreadService(USER_ID, mock_client)
        result = svc.list_threads()

        assert result == []

    def test_list_threads_returns_ordered(self) -> None:
        """Returns list of ConversationThread objects."""
        rows = [
            _thread_row(thread_id=f"user:{USER_ID}:111", title="Thread 1"),
            _thread_row(thread_id=f"user:{USER_ID}:222", title="Thread 2"),
        ]
        mock_client, mock_table = _make_mock_client(rows)

        svc = ThreadService(USER_ID, mock_client)
        result = svc.list_threads()

        assert len(result) == 2
        assert all(isinstance(t, ConversationThread) for t in result)
        assert result[0].title == "Thread 1"
        assert result[1].title == "Thread 2"
        mock_table.order.assert_called_once_with("updated_at", desc=True)


# =============================================================================
# Get
# =============================================================================


class TestGetThread:
    """Tests for ThreadService.get_thread."""

    def test_get_thread_found(self) -> None:
        """Returns ConversationThread when thread exists."""
        tid = f"user:{USER_ID}:some-uuid"
        row = _thread_row(thread_id=tid, title="My chat")
        mock_client, _ = _make_mock_client([row])

        svc = ThreadService(USER_ID, mock_client)
        result = svc.get_thread(tid)

        assert result is not None
        assert isinstance(result, ConversationThread)
        assert result.thread_id == tid
        assert result.title == "My chat"

    def test_get_thread_not_found(self) -> None:
        """Returns None when thread does not exist."""
        mock_client, _ = _make_mock_client([])

        svc = ThreadService(USER_ID, mock_client)
        result = svc.get_thread("user:xyz:nonexistent")

        assert result is None


# =============================================================================
# Update title
# =============================================================================


class TestUpdateTitle:
    """Tests for ThreadService.update_title."""

    def test_update_title(self) -> None:
        """Calls update with correct title and updated_at."""
        mock_client, mock_table = _make_mock_client()
        tid = f"user:{USER_ID}:abc"

        svc = ThreadService(USER_ID, mock_client)
        svc.update_title(tid, "Renamed thread")

        update_call = mock_table.update.call_args[0][0]
        assert update_call["title"] == "Renamed thread"
        assert "updated_at" in update_call
        mock_table.execute.assert_called_once()


# =============================================================================
# Touch
# =============================================================================


class TestTouch:
    """Tests for ThreadService.touch."""

    def test_touch(self) -> None:
        """Calls update with updated_at timestamp."""
        mock_client, mock_table = _make_mock_client()
        tid = f"user:{USER_ID}:abc"

        svc = ThreadService(USER_ID, mock_client)
        svc.touch(tid)

        update_call = mock_table.update.call_args[0][0]
        assert "updated_at" in update_call
        assert "title" not in update_call
        mock_table.execute.assert_called_once()


# =============================================================================
# Delete
# =============================================================================


class TestDeleteThread:
    """Tests for ThreadService.delete_thread."""

    def test_delete_thread(self) -> None:
        """Calls delete chain with correct user_id and thread_id filters."""
        mock_client, mock_table = _make_mock_client()
        tid = f"user:{USER_ID}:abc"

        svc = ThreadService(USER_ID, mock_client)
        svc.delete_thread(tid)

        # delete is called for the metadata row AND the 3 checkpoint tables
        assert mock_table.delete.call_count >= 1
        # Verify eq was called for both user_id and thread_id filtering on the metadata row
        eq_calls = [call[0] for call in mock_table.eq.call_args_list]
        assert ("user_id", USER_ID) in eq_calls
        assert ("thread_id", tid) in eq_calls


# =============================================================================
# Delete — checkpoint cleanup
# =============================================================================


class TestDeleteThreadCleansCheckpoints:
    """Tests that delete_thread also removes associated LangGraph checkpoint rows."""

    def test_delete_thread_also_deletes_checkpoint_tables(self) -> None:
        """Deleting a thread also purges checkpoint_writes, checkpoint_blobs, checkpoints."""
        mock_client, mock_table = _make_mock_client()
        tid = "user:test-user-123:abc-def"

        svc = ThreadService(USER_ID, mock_client)
        svc.delete_thread(tid)

        # Collect every table name passed to mock_client.table(...)
        table_calls = [call[0][0] for call in mock_client.table.call_args_list]
        assert "checkpoint_writes" in table_calls
        assert "checkpoint_blobs" in table_calls
        assert "checkpoints" in table_calls

        # For each checkpoint table, verify .eq("thread_id", tid) was called
        eq_calls = [call[0] for call in mock_table.eq.call_args_list]
        # There should be at least 3 eq("thread_id", tid) calls — one per checkpoint table
        thread_id_eq_calls = [c for c in eq_calls if c == ("thread_id", tid)]
        assert len(thread_id_eq_calls) >= 3, (
            f"Expected eq('thread_id', tid) at least 3 times, got: {thread_id_eq_calls}"
        )
