"""Tests for services, seed, auth, and supabase_client coverage gaps.

Targets:
- src/services/levels.py (lines 90-112, 139, 157-187)
- src/db/seed.py (0% coverage - all lines)
- src/api/supabase_client.py (lines 91-106)
- src/api/auth.py (EffectiveUser, get_effective_user, get_client_for_user)
- src/agent/checkpointer.py (postgres success path)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.levels import (
    CEFRLevel,
    LevelAssessment,
    LevelService,
    PerformanceMetrics,
)

# =============================================================================
# LevelService.assess_level() Tests (lines 90-118)
# =============================================================================


class TestLevelServiceAssessLevel:
    """Tests for LevelService.assess_level covering upgrade, downgrade, and no-change paths."""

    def setup_method(self) -> None:
        self.service = LevelService()

    def test_upgrade_when_consecutive_correct_meets_threshold(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=5, consecutive_errors=0,
            grammar_error_rate=0.1, vocabulary_use_rate=0.8, message_complexity=0.6,
        )
        result = self.service.assess_level(CEFRLevel.A1, metrics)
        assert result.should_adjust is True
        assert result.suggested_level == CEFRLevel.A2
        assert "readiness for more challenge" in result.reasoning

    def test_upgrade_confidence_calculation(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=5, consecutive_errors=0,
            grammar_error_rate=0.1, vocabulary_use_rate=0.8, message_complexity=0.6,
        )
        result = self.service.assess_level(CEFRLevel.A0, metrics)
        # min(0.9, 0.5 + 5 * 0.1) = min(0.9, 1.0) = 0.9
        assert result.confidence == 0.9

    def test_no_upgrade_when_at_highest_level(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=10, consecutive_errors=0,
            grammar_error_rate=0.0, vocabulary_use_rate=1.0, message_complexity=1.0,
        )
        result = self.service.assess_level(CEFRLevel.B1, metrics)
        assert result.should_adjust is False
        assert result.suggested_level is None

    def test_upgrade_from_a2_to_b1(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=6, consecutive_errors=0,
            grammar_error_rate=0.05, vocabulary_use_rate=0.85, message_complexity=0.7,
        )
        result = self.service.assess_level(CEFRLevel.A2, metrics)
        assert result.suggested_level == CEFRLevel.B1
        assert result.should_adjust is True

    def test_downgrade_when_consecutive_errors_meets_threshold(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=0, consecutive_errors=3,
            grammar_error_rate=0.5, vocabulary_use_rate=0.2, message_complexity=0.1,
        )
        result = self.service.assess_level(CEFRLevel.A2, metrics)
        assert result.suggested_level == CEFRLevel.A1
        assert result.should_adjust is True
        assert "too challenging" in result.reasoning

    def test_downgrade_confidence_capped(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=0, consecutive_errors=4,
            grammar_error_rate=0.6, vocabulary_use_rate=0.1, message_complexity=0.1,
        )
        result = self.service.assess_level(CEFRLevel.B1, metrics)
        # min(0.9, 0.5 + 4 * 0.1) = 0.9
        assert result.confidence == 0.9
        assert result.suggested_level == CEFRLevel.A2

    def test_downgrade_confidence_below_cap(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=0, consecutive_errors=3,
            grammar_error_rate=0.5, vocabulary_use_rate=0.2, message_complexity=0.1,
        )
        result = self.service.assess_level(CEFRLevel.A1, metrics)
        # min(0.9, 0.5 + 3 * 0.1) = 0.8
        assert result.confidence == 0.8
        assert result.suggested_level == CEFRLevel.A0

    def test_no_downgrade_when_at_lowest_level(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=0, consecutive_errors=10,
            grammar_error_rate=0.9, vocabulary_use_rate=0.0, message_complexity=0.0,
        )
        result = self.service.assess_level(CEFRLevel.A0, metrics)
        assert result.should_adjust is False
        assert result.suggested_level is None

    def test_no_change_when_below_thresholds(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=3, consecutive_errors=1,
            grammar_error_rate=0.2, vocabulary_use_rate=0.6, message_complexity=0.5,
        )
        result = self.service.assess_level(CEFRLevel.A1, metrics)
        assert result.should_adjust is False
        assert result.suggested_level is None
        assert result.confidence == 0.8
        assert "appropriate for current level" in result.reasoning

    def test_upgrade_takes_priority_over_downgrade(self) -> None:
        metrics = PerformanceMetrics(
            consecutive_correct=5, consecutive_errors=3,
            grammar_error_rate=0.3, vocabulary_use_rate=0.5, message_complexity=0.5,
        )
        result = self.service.assess_level(CEFRLevel.A1, metrics)
        assert result.suggested_level == CEFRLevel.A2
        assert result.should_adjust is True


# =============================================================================
# LevelService.detect_initial_level() Tests (line 139)
# =============================================================================


class TestLevelServiceDetectInitialLevel:
    """Tests for LevelService.detect_initial_level stub."""

    def setup_method(self) -> None:
        self.service = LevelService()

    def test_returns_a0_for_any_text(self) -> None:
        result = self.service.detect_initial_level("Hola, me llamo Juan.", "es")
        assert isinstance(result, LevelAssessment)
        assert result.current_level == CEFRLevel.A0
        assert result.suggested_level == CEFRLevel.A0
        assert result.should_adjust is False
        assert result.confidence == 0.5

    def test_returns_a0_for_empty_text(self) -> None:
        result = self.service.detect_initial_level("", "es")
        assert result.current_level == CEFRLevel.A0

    def test_returns_a0_regardless_of_language(self) -> None:
        result = self.service.detect_initial_level("Bonjour le monde", "fr")
        assert result.current_level == CEFRLevel.A0


# =============================================================================
# LevelService.get_scaffolding_requirements() Tests (lines 157-187)
# =============================================================================


class TestLevelServiceGetScaffoldingRequirements:
    """Tests for LevelService.get_scaffolding_requirements for all CEFR levels."""

    def setup_method(self) -> None:
        self.service = LevelService()

    def test_a0_scaffolding_all_features_enabled(self) -> None:
        result = self.service.get_scaffolding_requirements(CEFRLevel.A0)
        assert result["show_word_bank"] is True
        assert result["show_translation"] is True
        assert result["show_hints"] is True
        assert result["show_sentence_starter"] is True
        assert result["auto_show_help"] is True

    def test_a1_scaffolding_partial_features(self) -> None:
        result = self.service.get_scaffolding_requirements(CEFRLevel.A1)
        assert result["show_word_bank"] is True
        assert result["show_sentence_starter"] is False
        assert result["auto_show_help"] is False

    def test_a2_scaffolding_translation_only(self) -> None:
        result = self.service.get_scaffolding_requirements(CEFRLevel.A2)
        assert result["show_word_bank"] is False
        assert result["show_translation"] is True
        assert result["show_hints"] is False

    def test_b1_scaffolding_no_features(self) -> None:
        result = self.service.get_scaffolding_requirements(CEFRLevel.B1)
        assert all(v is False for v in result.values())

    def test_all_levels_return_five_keys(self) -> None:
        expected_keys = {
            "show_word_bank", "show_translation", "show_hints",
            "show_sentence_starter", "auto_show_help",
        }
        for level in CEFRLevel:
            result = self.service.get_scaffolding_requirements(level)
            assert set(result.keys()) == expected_keys

    def test_scaffolding_decreases_with_level(self) -> None:
        counts = {}
        for level in CEFRLevel:
            result = self.service.get_scaffolding_requirements(level)
            counts[level] = sum(1 for v in result.values() if v)
        assert counts[CEFRLevel.A0] > counts[CEFRLevel.A1]
        assert counts[CEFRLevel.A1] > counts[CEFRLevel.A2]
        assert counts[CEFRLevel.A2] > counts[CEFRLevel.B1]


# =============================================================================
# src/db/seed.py Tests (0% coverage)
# =============================================================================


class TestEnsureUserProfile:
    """Tests for ensure_user_profile function."""

    def test_no_op_when_profile_exists(self) -> None:
        with patch("src.db.seed.UserProfileRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get.return_value = MagicMock()  # profile exists
            mock_repo_cls.return_value = mock_repo

            from src.db.seed import ensure_user_profile
            ensure_user_profile("user-123")

            mock_repo.get.assert_called_once()

    def test_no_op_does_not_call_supabase(self) -> None:
        with (
            patch("src.db.seed.UserProfileRepository") as mock_repo_cls,
            patch("src.db.seed.get_supabase") as mock_get_supabase,
        ):
            mock_repo = MagicMock()
            mock_repo.get.return_value = MagicMock()  # profile exists
            mock_repo_cls.return_value = mock_repo

            from src.db.seed import ensure_user_profile
            ensure_user_profile("user-123")

            mock_get_supabase.assert_not_called()

    def test_creates_profile_when_missing(self) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table

        with (
            patch("src.db.seed.UserProfileRepository") as mock_repo_cls,
            patch("src.db.seed.get_supabase", return_value=mock_client),
        ):
            mock_repo = MagicMock()
            mock_repo.get.return_value = None  # profile missing
            mock_repo_cls.return_value = mock_repo

            from src.db.seed import ensure_user_profile
            ensure_user_profile("user-456")

            mock_client.table.assert_called_once_with("user_profiles")
            mock_table.insert.assert_called_once_with({
                "id": "user-456",
                "preferred_language": "es",
                "current_level": "A1",
            })


class TestResetUserData:
    """Tests for reset_user_data function."""

    def test_deletes_vocabulary_sessions_and_progress(self) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.delete.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table

        with patch("src.db.seed.get_supabase", return_value=mock_client):
            from src.db.seed import reset_user_data
            reset_user_data("user-789")

        table_calls = [call[0][0] for call in mock_client.table.call_args_list]
        assert "vocabulary" in table_calls
        assert "learning_sessions" in table_calls
        assert "lesson_progress" in table_calls
        assert mock_client.table.call_count == 3


class TestSeedModuleConstants:
    """Tests for seed module constants."""

    def test_default_user_settings(self) -> None:
        from src.db.seed import DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["preferred_language"] == "es"
        assert DEFAULT_USER_SETTINGS["current_level"] == "A1"


# =============================================================================
# src/api/supabase_client.py - get_supabase_for_user() Tests
# =============================================================================


class TestGetSupabaseForUser:
    """Tests for get_supabase_for_user function."""

    def test_raises_when_not_configured(self) -> None:
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = False
            from src.api.supabase_client import get_supabase_for_user
            with pytest.raises(ValueError, match="not configured"):
                get_supabase_for_user("some-access-token")

    def test_returns_client_with_user_auth(self) -> None:
        mock_client = MagicMock()
        with (
            patch("src.api.supabase_client.get_settings") as mock_settings,
            patch("src.api.supabase_client.create_client", return_value=mock_client),
        ):
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "test-anon-key"

            from src.api.supabase_client import get_supabase_for_user
            result = get_supabase_for_user("user-jwt-token")

        assert result is mock_client
        mock_client.postgrest.auth.assert_called_once_with("user-jwt-token")

    def test_creates_client_with_correct_credentials(self) -> None:
        mock_client = MagicMock()
        with (
            patch("src.api.supabase_client.get_settings") as mock_settings,
            patch("src.api.supabase_client.create_client", return_value=mock_client) as mock_create,
        ):
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://myproject.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "my-anon-key"

            from src.api.supabase_client import get_supabase_for_user
            get_supabase_for_user("token-abc")

        mock_create.assert_called_once_with("https://myproject.supabase.co", "my-anon-key")


# =============================================================================
# src/api/auth.py - EffectiveUser, get_effective_user, get_client_for_user
# =============================================================================


class TestEffectiveUser:
    """Tests for the EffectiveUser dataclass."""

    def test_create_authenticated_effective_user(self) -> None:
        from src.api.auth import EffectiveUser
        user = EffectiveUser(id="user-123", is_guest=False, email="test@example.com")
        assert user.id == "user-123"
        assert user.is_guest is False
        assert user.email == "test@example.com"

    def test_create_guest_effective_user(self) -> None:
        from src.api.auth import EffectiveUser
        user = EffectiveUser(id="session-abc", is_guest=True)
        assert user.id == "session-abc"
        assert user.is_guest is True
        assert user.email is None

    def test_effective_user_is_frozen(self) -> None:
        from src.api.auth import EffectiveUser
        user = EffectiveUser(id="user-123", is_guest=False)
        with pytest.raises(AttributeError):
            user.id = "changed"  # type: ignore[misc]


class TestGetEffectiveUser:
    """Tests for get_effective_user dependency."""

    @pytest.mark.asyncio
    async def test_returns_authenticated_effective_user(self) -> None:
        from src.api.auth import AuthenticatedUser, EffectiveUser, get_effective_user
        request = MagicMock()
        auth_user = AuthenticatedUser(id="auth-user-id", email="auth@test.com")
        result = await get_effective_user(request, user=auth_user)
        assert isinstance(result, EffectiveUser)
        assert result.id == "auth-user-id"
        assert result.is_guest is False

    @pytest.mark.asyncio
    async def test_returns_guest_effective_user_from_session_cookie(self) -> None:
        from src.api.auth import EffectiveUser, get_effective_user
        request = MagicMock()
        request.cookies.get.return_value = "guest-session-id-456"
        result = await get_effective_user(request, user=None)
        assert isinstance(result, EffectiveUser)
        assert result.id == "guest-session-id-456"
        assert result.is_guest is True

    @pytest.mark.asyncio
    async def test_returns_none_when_no_identity(self) -> None:
        from src.api.auth import get_effective_user
        request = MagicMock()
        request.cookies.get.return_value = None
        result = await get_effective_user(request, user=None)
        assert result is None


class TestGetClientForUser:
    """Tests for get_client_for_user function."""

    def test_returns_admin_client_for_guest(self) -> None:
        from src.api.auth import EffectiveUser, get_client_for_user
        guest = EffectiveUser(id="session-abc", is_guest=True)
        mock_admin_client = MagicMock()
        with patch("src.api.auth.get_supabase_admin", return_value=mock_admin_client):
            result = get_client_for_user(guest)
        assert result is mock_admin_client

    def test_returns_anon_client_for_authenticated(self) -> None:
        from src.api.auth import EffectiveUser, get_client_for_user
        auth_user = EffectiveUser(id="user-123", is_guest=False)
        mock_anon_client = MagicMock()
        with patch("src.api.auth.get_supabase", return_value=mock_anon_client):
            result = get_client_for_user(auth_user)
        assert result is mock_anon_client


# =============================================================================
# src/agent/checkpointer.py - get_postgres_checkpointer success path
# =============================================================================


class TestGetPostgresCheckpointerSuccessPath:
    """Tests for get_postgres_checkpointer when SUPABASE_DB_URL is configured."""

    @pytest.mark.asyncio
    async def test_creates_postgres_saver_and_calls_setup(self) -> None:
        from src.api.config import Settings

        mock_settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-anon-key",
            SUPABASE_DB_URL="postgresql://user:pass@localhost:5432/test",
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("src.agent.checkpointer.get_settings", return_value=mock_settings),
            patch(
                "src.agent.checkpointer.AsyncPostgresSaver.from_conn_string",
                return_value=mock_context_manager,
            ) as mock_from_conn,
        ):
            from src.agent.checkpointer import get_postgres_checkpointer
            async with get_postgres_checkpointer() as checkpointer:
                assert checkpointer is mock_checkpointer
            mock_from_conn.assert_called_once_with("postgresql://user:pass@localhost:5432/test")
            mock_checkpointer.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_checkpointer_delegates_to_postgres_when_valid_url(self) -> None:
        from src.api.config import Settings

        mock_settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-anon-key",
            SUPABASE_DB_URL="postgresql://user:pass@db.supabase.co:5432/postgres",
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("src.agent.checkpointer.get_settings", return_value=mock_settings),
            patch(
                "src.agent.checkpointer.AsyncPostgresSaver.from_conn_string",
                return_value=mock_context_manager,
            ),
        ):
            from src.agent.checkpointer import get_checkpointer
            async with get_checkpointer() as checkpointer:
                assert checkpointer is mock_checkpointer

    @pytest.mark.asyncio
    async def test_get_checkpointer_falls_back_for_placeholder_url(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        from src.agent.checkpointer import clear_memory_saver
        from src.api.config import Settings

        mock_settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-anon-key",
            SUPABASE_DB_URL="postgresql://postgres.[PROJECT-REF]:password@db.supabase.co:5432/postgres",
        )

        clear_memory_saver()

        with patch("src.agent.checkpointer.get_settings", return_value=mock_settings):
            from src.agent.checkpointer import get_checkpointer
            async with get_checkpointer() as checkpointer:
                assert isinstance(checkpointer, MemorySaver)
