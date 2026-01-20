"""Tests for Supabase client module.

Tests for client singleton and cache management.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.api.supabase_client import (
    clear_supabase_cache,
    get_supabase,
    get_supabase_admin,
)

# =============================================================================
# get_supabase Tests
# =============================================================================


class TestGetSupabase:
    """Tests for get_supabase function."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_supabase_cache()

    def test_raises_when_not_configured(self) -> None:
        """Test raises ValueError when Supabase not configured."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = False

            with pytest.raises(ValueError) as exc_info:
                get_supabase()

            assert "not configured" in str(exc_info.value)
            assert "SUPABASE_URL" in str(exc_info.value)

    def test_returns_client_when_configured(self) -> None:
        """Test returns Supabase client when configured."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "test-anon-key"

            with patch("supabase.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client

                result = get_supabase()

                assert result == mock_client
                mock_create.assert_called_once_with("https://test.supabase.co", "test-anon-key")

    def test_caches_client_instance(self) -> None:
        """Test client is cached across calls."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "test-anon-key"

            with patch("supabase.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client

                result1 = get_supabase()
                result2 = get_supabase()

                assert result1 is result2
                # create_client should only be called once due to caching
                mock_create.assert_called_once()


# =============================================================================
# get_supabase_admin Tests
# =============================================================================


class TestGetSupabaseAdmin:
    """Tests for get_supabase_admin function."""

    def test_raises_when_not_configured(self) -> None:
        """Test raises ValueError when Supabase not configured."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = False

            with pytest.raises(ValueError) as exc_info:
                get_supabase_admin()

            assert "not configured" in str(exc_info.value)

    def test_raises_when_service_key_missing(self) -> None:
        """Test raises ValueError when service key is missing."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_SERVICE_KEY = ""

            with pytest.raises(ValueError) as exc_info:
                get_supabase_admin()

            assert "SUPABASE_SERVICE_KEY" in str(exc_info.value)

    def test_returns_admin_client_when_configured(self) -> None:
        """Test returns admin client when fully configured."""
        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_SERVICE_KEY = "service-key"

            with patch("supabase.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client

                result = get_supabase_admin()

                assert result == mock_client
                mock_create.assert_called_once_with("https://test.supabase.co", "service-key")


# =============================================================================
# Cache Management Tests
# =============================================================================


class TestClearSupabaseCache:
    """Tests for clear_supabase_cache function."""

    def test_clears_cache(self) -> None:
        """Test cache is cleared."""
        # Clear any existing cache first
        clear_supabase_cache()

        with patch("src.api.supabase_client.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "test-anon-key"

            with patch("supabase.create_client") as mock_create:
                mock_client1 = MagicMock()
                mock_client2 = MagicMock()
                mock_create.side_effect = [mock_client1, mock_client2]

                # First call
                result1 = get_supabase()
                assert result1 == mock_client1
                assert mock_create.call_count == 1

                # Clear cache
                clear_supabase_cache()

                # Second call should create new client
                result2 = get_supabase()
                assert result2 == mock_client2
                assert mock_create.call_count == 2

    def test_cache_info(self) -> None:
        """Test get_supabase has cache_info attribute."""
        # lru_cache decorated functions have cache_info
        assert hasattr(get_supabase, "cache_info")

    def test_cache_clear(self) -> None:
        """Test get_supabase has cache_clear attribute."""
        # lru_cache decorated functions have cache_clear
        assert hasattr(get_supabase, "cache_clear")
