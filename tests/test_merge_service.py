"""Tests for GuestDataMergeService.

Comprehensive tests for merging guest session data into authenticated
user accounts during signup/login, covering vocabulary, sessions,
lessons, error resilience, and auth route trigger integration.
"""

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.merge import GuestDataMergeService

# =============================================================================
# Test Helpers
# =============================================================================

GUEST_ID = "guest-session-abc-123"
AUTH_ID = "auth-user-xyz-789"


def make_chainable_table(data: list[dict[str, Any]] | None = None) -> MagicMock:
    """Create a mock table object supporting chained Supabase calls.

    Supports patterns like:
        client.table("x").select("*").eq("a", "b").eq("c", "d").execute()

    Args:
        data: The data to return from .execute().data. Defaults to empty list.

    Returns:
        MagicMock: Chainable mock table with .execute() returning mock response.
    """
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.single.return_value = mock_table

    response = MagicMock()
    response.data = data if data is not None else []
    mock_table.execute.return_value = response

    return mock_table


def make_mock_client(table_responses: dict[str, list[MagicMock]] | None = None) -> MagicMock:
    """Create a mock Supabase admin client with per-table response sequences.

    Each call to client.table("name") returns the next chainable mock table
    from the table_responses sequence for that table name.

    Args:
        table_responses: Mapping of table name to list of chainable mock tables
            to return in order. If None, returns empty-data tables.

    Returns:
        MagicMock: Mock Supabase client with .table() method.
    """
    mock_client = MagicMock()
    table_call_counts: dict[str, int] = {}

    def table_side_effect(table_name: str) -> MagicMock:
        """Return the next mock table for the given table name."""
        if table_responses and table_name in table_responses:
            idx = table_call_counts.get(table_name, 0)
            tables = table_responses[table_name]
            result = tables[idx] if idx < len(tables) else tables[-1]
            table_call_counts[table_name] = idx + 1
            return result
        return make_chainable_table()

    mock_client.table.side_effect = table_side_effect
    return mock_client


# =============================================================================
# TestMergeVocabulary
# =============================================================================


class TestMergeVocabulary:
    """Tests for GuestDataMergeService._merge_vocabulary."""

    @patch("src.services.merge.get_supabase_admin")
    def test_transfers_unique_vocab(self, mock_get_admin: MagicMock) -> None:
        """Guest has words the auth user does not -- verify user_id update."""
        guest_entry = {
            "id": "v1",
            "user_id": GUEST_ID,
            "word": "hola",
            "language": "es",
            "times_seen": 3,
            "times_correct": 2,
            "first_seen_at": "2025-01-01T00:00:00Z",
        }

        # First table("vocabulary") call: select guest vocab -> returns entry
        guest_table = make_chainable_table([guest_entry])
        # Second call: select auth user's matching word -> no match
        auth_lookup_table = make_chainable_table([])
        # Third call: update user_id (transfer ownership)
        transfer_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "vocabulary": [guest_table, auth_lookup_table, transfer_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_vocabulary()

        assert count == 1
        # Verify the transfer call: update({"user_id": AUTH_ID}).eq("id", "v1")
        transfer_table.update.assert_called_once_with({"user_id": AUTH_ID})

    @patch("src.services.merge.get_supabase_admin")
    def test_merges_duplicate_counters(self, mock_get_admin: MagicMock) -> None:
        """Guest and auth both have 'hola' in 'es' -- counters summed, earliest date kept."""
        guest_entry = {
            "id": "v-guest",
            "user_id": GUEST_ID,
            "word": "hola",
            "language": "es",
            "times_seen": 5,
            "times_correct": 3,
            "first_seen_at": "2025-01-01T00:00:00Z",
        }
        auth_entry = {
            "id": "v-auth",
            "user_id": AUTH_ID,
            "word": "hola",
            "language": "es",
            "times_seen": 10,
            "times_correct": 7,
            "first_seen_at": "2025-01-15T00:00:00Z",
        }

        # Call 1: select guest vocab
        guest_table = make_chainable_table([guest_entry])
        # Call 2: select auth matching word -> found duplicate
        auth_lookup_table = make_chainable_table([auth_entry])
        # Call 3: update merged counters on auth entry
        merge_update_table = make_chainable_table()
        # Call 4: delete guest entry
        delete_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "vocabulary": [guest_table, auth_lookup_table, merge_update_table, delete_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_vocabulary()

        assert count == 1

        # Verify merged counter values
        merge_update_table.update.assert_called_once_with(
            {
                "times_seen": 15,  # 10 + 5
                "times_correct": 10,  # 7 + 3
                "first_seen_at": "2025-01-01T00:00:00Z",  # min of the two
            }
        )

        # Verify guest entry was deleted
        delete_table.delete.assert_called_once()

    @patch("src.services.merge.get_supabase_admin")
    def test_no_guest_vocab(self, mock_get_admin: MagicMock) -> None:
        """Guest has no vocabulary entries -- returns 0 with no updates."""
        guest_table = make_chainable_table([])

        mock_client = make_mock_client({"vocabulary": [guest_table]})
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_vocabulary()

        assert count == 0
        # Only one table call (the initial select)
        assert mock_client.table.call_count == 1

    @patch("src.services.merge.get_supabase_admin")
    def test_multiple_entries(self, mock_get_admin: MagicMock) -> None:
        """Guest has 3 vocab entries, 1 is a duplicate -- verify correct counts."""
        guest_entries = [
            {
                "id": "v1",
                "user_id": GUEST_ID,
                "word": "hola",
                "language": "es",
                "times_seen": 2,
                "times_correct": 1,
                "first_seen_at": "2025-01-10T00:00:00Z",
            },
            {
                "id": "v2",
                "user_id": GUEST_ID,
                "word": "gracias",
                "language": "es",
                "times_seen": 4,
                "times_correct": 3,
                "first_seen_at": "2025-01-05T00:00:00Z",
            },
            {
                "id": "v3",
                "user_id": GUEST_ID,
                "word": "buenos",
                "language": "es",
                "times_seen": 1,
                "times_correct": 0,
                "first_seen_at": "2025-01-20T00:00:00Z",
            },
        ]
        auth_hola_entry = {
            "id": "v-auth-hola",
            "user_id": AUTH_ID,
            "word": "hola",
            "language": "es",
            "times_seen": 3,
            "times_correct": 2,
            "first_seen_at": "2025-01-01T00:00:00Z",
        }

        # Call sequence for vocabulary table:
        # 1: select all guest vocab -> 3 entries
        guest_table = make_chainable_table(guest_entries)
        # 2: lookup "hola" for auth -> found (duplicate)
        lookup_hola = make_chainable_table([auth_hola_entry])
        # 3: update merged counters for "hola"
        merge_hola = make_chainable_table()
        # 4: delete guest "hola" entry
        delete_hola = make_chainable_table()
        # 5: lookup "gracias" for auth -> not found
        lookup_gracias = make_chainable_table([])
        # 6: transfer "gracias" ownership
        transfer_gracias = make_chainable_table()
        # 7: lookup "buenos" for auth -> not found
        lookup_buenos = make_chainable_table([])
        # 8: transfer "buenos" ownership
        transfer_buenos = make_chainable_table()

        mock_client = make_mock_client(
            {
                "vocabulary": [
                    guest_table,
                    lookup_hola,
                    merge_hola,
                    delete_hola,
                    lookup_gracias,
                    transfer_gracias,
                    lookup_buenos,
                    transfer_buenos,
                ],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_vocabulary()

        assert count == 3
        # Verify: 1 merge update + 2 ownership transfers
        transfer_gracias.update.assert_called_once_with({"user_id": AUTH_ID})
        transfer_buenos.update.assert_called_once_with({"user_id": AUTH_ID})


# =============================================================================
# TestMergeSessions
# =============================================================================


class TestMergeSessions:
    """Tests for GuestDataMergeService._merge_sessions."""

    @patch("src.services.merge.get_supabase_admin")
    def test_transfers_all_sessions(self, mock_get_admin: MagicMock) -> None:
        """Guest has 2 sessions -- both get user_id updated."""
        guest_sessions = [{"id": "s1"}, {"id": "s2"}]

        # Call 1: select guest sessions -> 2 entries
        select_table = make_chainable_table(guest_sessions)
        # Call 2: bulk update user_id
        update_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "learning_sessions": [select_table, update_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_sessions()

        assert count == 2
        update_table.update.assert_called_once_with({"user_id": AUTH_ID})

    @patch("src.services.merge.get_supabase_admin")
    def test_no_guest_sessions(self, mock_get_admin: MagicMock) -> None:
        """Guest has no sessions -- returns 0."""
        select_table = make_chainable_table([])

        mock_client = make_mock_client({"learning_sessions": [select_table]})
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_sessions()

        assert count == 0
        # Only one table call (the select)
        assert mock_client.table.call_count == 1

    @patch("src.services.merge.get_supabase_admin")
    def test_bulk_transfer(self, mock_get_admin: MagicMock) -> None:
        """Verifies a single bulk update call is made, not per-session."""
        guest_sessions = [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]

        select_table = make_chainable_table(guest_sessions)
        update_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "learning_sessions": [select_table, update_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_sessions()

        assert count == 3
        # Exactly 2 table calls: one select, one bulk update
        learning_calls = [
            c for c in mock_client.table.call_args_list if c == call("learning_sessions")
        ]
        assert len(learning_calls) == 2
        # Only one update call (bulk, not per-session)
        update_table.update.assert_called_once()


# =============================================================================
# TestMergeLessons
# =============================================================================


class TestMergeLessons:
    """Tests for GuestDataMergeService._merge_lessons."""

    @patch("src.services.merge.get_supabase_admin")
    def test_transfers_unique_lessons(self, mock_get_admin: MagicMock) -> None:
        """Guest has lessons the auth user does not -- verify user_id update."""
        guest_lesson = {
            "id": "lp1",
            "user_id": GUEST_ID,
            "lesson_id": "lesson-basics-1",
            "score": 85,
        }

        # Call 1: select guest lessons
        guest_table = make_chainable_table([guest_lesson])
        # Call 2: lookup existing auth lesson -> not found
        auth_lookup = make_chainable_table([])
        # Call 3: transfer ownership
        transfer_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "lesson_progress": [guest_table, auth_lookup, transfer_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_lessons()

        assert count == 1
        transfer_table.update.assert_called_once_with({"user_id": AUTH_ID})

    @patch("src.services.merge.get_supabase_admin")
    def test_keeps_higher_score(self, mock_get_admin: MagicMock) -> None:
        """Guest score 90 > auth score 70 -- auth score updated, guest deleted."""
        guest_lesson = {
            "id": "lp-guest",
            "user_id": GUEST_ID,
            "lesson_id": "lesson-greetings",
            "score": 90,
        }
        auth_lesson = {
            "id": "lp-auth",
            "user_id": AUTH_ID,
            "lesson_id": "lesson-greetings",
            "score": 70,
        }

        # Call 1: select guest lessons
        guest_table = make_chainable_table([guest_lesson])
        # Call 2: lookup auth lesson -> found (duplicate)
        auth_lookup = make_chainable_table([auth_lesson])
        # Call 3: update auth score to guest's higher score
        score_update_table = make_chainable_table()
        # Call 4: delete guest entry
        delete_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "lesson_progress": [guest_table, auth_lookup, score_update_table, delete_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_lessons()

        assert count == 1
        score_update_table.update.assert_called_once_with({"score": 90})
        delete_table.delete.assert_called_once()

    @patch("src.services.merge.get_supabase_admin")
    def test_keeps_auth_score_when_higher(self, mock_get_admin: MagicMock) -> None:
        """Guest score 60 < auth score 80 -- no score update, guest deleted."""
        guest_lesson = {
            "id": "lp-guest",
            "user_id": GUEST_ID,
            "lesson_id": "lesson-numbers",
            "score": 60,
        }
        auth_lesson = {
            "id": "lp-auth",
            "user_id": AUTH_ID,
            "lesson_id": "lesson-numbers",
            "score": 80,
        }

        # Call 1: select guest lessons
        guest_table = make_chainable_table([guest_lesson])
        # Call 2: lookup auth lesson -> found
        auth_lookup = make_chainable_table([auth_lesson])
        # Call 3: delete guest entry (no score update needed)
        delete_table = make_chainable_table()

        mock_client = make_mock_client(
            {
                "lesson_progress": [guest_table, auth_lookup, delete_table],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_lessons()

        assert count == 1
        # No score update should occur -- only the delete
        delete_table.delete.assert_called_once()
        # The delete_table should NOT have had update called on it
        delete_table.update.assert_not_called()

    @patch("src.services.merge.get_supabase_admin")
    def test_no_guest_lessons(self, mock_get_admin: MagicMock) -> None:
        """Guest has no lesson progress -- returns 0."""
        guest_table = make_chainable_table([])

        mock_client = make_mock_client({"lesson_progress": [guest_table]})
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        count = service._merge_lessons()

        assert count == 0
        assert mock_client.table.call_count == 1


# =============================================================================
# TestMergeAll
# =============================================================================


class TestMergeAll:
    """Tests for GuestDataMergeService.merge_all orchestration."""

    @patch("src.services.merge.get_supabase_admin")
    def test_merge_all_returns_counts(self, mock_get_admin: MagicMock) -> None:
        """All 3 merges return expected counts in the result dict."""
        guest_vocab = [
            {
                "id": "v1",
                "user_id": GUEST_ID,
                "word": "hola",
                "language": "es",
                "times_seen": 1,
                "times_correct": 1,
                "first_seen_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": "v2",
                "user_id": GUEST_ID,
                "word": "adios",
                "language": "es",
                "times_seen": 2,
                "times_correct": 1,
                "first_seen_at": "2025-01-02T00:00:00Z",
            },
        ]
        guest_sessions = [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]
        guest_lesson = {
            "id": "lp1",
            "user_id": GUEST_ID,
            "lesson_id": "lesson-1",
            "score": 75,
        }

        mock_client = make_mock_client(
            {
                # vocabulary: select guest -> 2 entries, then per-entry lookups and transfers
                "vocabulary": [
                    make_chainable_table(guest_vocab),  # select guest vocab
                    make_chainable_table([]),  # lookup "hola" -> not found
                    make_chainable_table(),  # transfer "hola"
                    make_chainable_table([]),  # lookup "adios" -> not found
                    make_chainable_table(),  # transfer "adios"
                ],
                # sessions: select + bulk update
                "learning_sessions": [
                    make_chainable_table(guest_sessions),  # select
                    make_chainable_table(),  # bulk update
                ],
                # lessons: select, lookup, transfer
                "lesson_progress": [
                    make_chainable_table([guest_lesson]),  # select
                    make_chainable_table([]),  # lookup -> not found
                    make_chainable_table(),  # transfer
                ],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        result = service.merge_all()

        assert result == {"vocabulary": 2, "sessions": 3, "lessons": 1}

    @patch("src.services.merge.get_supabase_admin")
    def test_merge_all_empty_guest(self, mock_get_admin: MagicMock) -> None:
        """All merge operations return 0 for a guest with no data."""
        mock_client = make_mock_client(
            {
                "vocabulary": [make_chainable_table([])],
                "learning_sessions": [make_chainable_table([])],
                "lesson_progress": [make_chainable_table([])],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)
        result = service.merge_all()

        assert result == {"vocabulary": 0, "sessions": 0, "lessons": 0}


# =============================================================================
# TestMergeErrorResilience
# =============================================================================


class TestMergeErrorResilience:
    """Tests for error propagation in GuestDataMergeService."""

    @patch("src.services.merge.get_supabase_admin")
    def test_merge_all_propagates_error(self, mock_get_admin: MagicMock) -> None:
        """If a merge operation fails, exception propagates from merge_all."""
        # Make the vocabulary select raise an exception
        failing_table = make_chainable_table()
        failing_table.execute.side_effect = Exception("DB connection failed")

        mock_client = make_mock_client({"vocabulary": [failing_table]})
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)

        with pytest.raises(Exception, match="DB connection failed"):
            service.merge_all()

    @patch("src.services.merge.get_supabase_admin")
    def test_vocab_merge_handles_db_error(self, mock_get_admin: MagicMock) -> None:
        """If an update call fails during vocab merge, exception propagates."""
        guest_entry = {
            "id": "v1",
            "user_id": GUEST_ID,
            "word": "hola",
            "language": "es",
            "times_seen": 1,
            "times_correct": 1,
            "first_seen_at": "2025-01-01T00:00:00Z",
        }

        guest_table = make_chainable_table([guest_entry])
        auth_lookup = make_chainable_table([])

        # Transfer table raises on execute
        failing_transfer = make_chainable_table()
        failing_transfer.execute.side_effect = Exception("Update failed: constraint violation")

        mock_client = make_mock_client(
            {
                "vocabulary": [guest_table, auth_lookup, failing_transfer],
            }
        )
        mock_get_admin.return_value = mock_client

        service = GuestDataMergeService(GUEST_ID, AUTH_ID)

        with pytest.raises(Exception, match="Update failed"):
            service._merge_vocabulary()


# =============================================================================
# TestAuthTrigger
# =============================================================================


class TestAuthTrigger:
    """Tests for merge trigger integration in auth routes."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the auth routes."""
        return TestClient(app)

    def _mock_successful_signup(self) -> MagicMock:
        """Create a mock for successful signup with session.

        Returns:
            MagicMock: Mock Supabase client with sign_up returning user+session.
        """
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.access_token = "test-access-token"
        mock_user = MagicMock()
        mock_user.id = AUTH_ID
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_response.session = mock_session
        mock_client.auth.sign_up.return_value = mock_response
        return mock_client

    def _mock_successful_login(self) -> MagicMock:
        """Create a mock for successful login with session.

        Returns:
            MagicMock: Mock Supabase client with sign_in_with_password returning user+session.
        """
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.access_token = "test-access-token"
        mock_user = MagicMock()
        mock_user.id = AUTH_ID
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_response.session = mock_session
        mock_client.auth.sign_in_with_password.return_value = mock_response
        return mock_client

    def test_signup_triggers_merge(self, client: TestClient) -> None:
        """Merge is called during signup when session_id cookie is present."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_get_client.return_value = self._mock_successful_signup()

            with patch("src.api.routes.auth.GuestDataMergeService") as mock_merge_cls:
                mock_merge_instance = MagicMock()
                mock_merge_instance.merge_all.return_value = {
                    "vocabulary": 2,
                    "sessions": 1,
                    "lessons": 0,
                }
                mock_merge_cls.return_value = mock_merge_instance

                response = client.post(
                    "/auth/signup",
                    data={
                        "email": "new@example.com",
                        "password": "securepass123",
                        "confirm_password": "securepass123",
                    },
                    cookies={"session_id": GUEST_ID},
                )

                assert response.status_code == 200
                mock_merge_cls.assert_called_once_with(
                    guest_session_id=GUEST_ID,
                    authenticated_user_id=AUTH_ID,
                )
                mock_merge_instance.merge_all.assert_called_once()

    def test_login_triggers_merge(self, client: TestClient) -> None:
        """Merge is called during login when session_id cookie is present."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_get_client.return_value = self._mock_successful_login()

            with patch("src.api.routes.auth.GuestDataMergeService") as mock_merge_cls:
                mock_merge_instance = MagicMock()
                mock_merge_instance.merge_all.return_value = {
                    "vocabulary": 1,
                    "sessions": 0,
                    "lessons": 3,
                }
                mock_merge_cls.return_value = mock_merge_instance

                response = client.post(
                    "/auth/login",
                    data={
                        "email": "existing@example.com",
                        "password": "securepass123",
                    },
                    cookies={"session_id": GUEST_ID},
                )

                assert response.status_code == 200
                mock_merge_cls.assert_called_once_with(
                    guest_session_id=GUEST_ID,
                    authenticated_user_id=AUTH_ID,
                )
                mock_merge_instance.merge_all.assert_called_once()

    def test_signup_no_merge_without_cookie(self, client: TestClient) -> None:
        """If no session_id cookie, merge is not triggered during signup."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_get_client.return_value = self._mock_successful_signup()

            with patch("src.api.routes.auth.GuestDataMergeService") as mock_merge_cls:
                response = client.post(
                    "/auth/signup",
                    data={
                        "email": "new@example.com",
                        "password": "securepass123",
                        "confirm_password": "securepass123",
                    },
                    # No session_id cookie
                )

                assert response.status_code == 200
                mock_merge_cls.assert_not_called()

    def test_signup_merge_failure_does_not_block(self, client: TestClient) -> None:
        """If merge_all raises, signup still succeeds (fire-and-forget)."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_get_client.return_value = self._mock_successful_signup()

            with patch("src.api.routes.auth.GuestDataMergeService") as mock_merge_cls:
                mock_merge_instance = MagicMock()
                mock_merge_instance.merge_all.side_effect = Exception("Database connection lost")
                mock_merge_cls.return_value = mock_merge_instance

                response = client.post(
                    "/auth/signup",
                    data={
                        "email": "new@example.com",
                        "password": "securepass123",
                        "confirm_password": "securepass123",
                    },
                    cookies={"session_id": GUEST_ID},
                )

                # Signup succeeds despite merge failure
                assert response.status_code == 200
                assert "HX-Redirect" in response.headers
                mock_merge_instance.merge_all.assert_called_once()
