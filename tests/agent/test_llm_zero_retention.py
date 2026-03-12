"""Tests for LLM zero-retention header configuration.

Verifies that the x-no-store header is conditionally set on ChatAnthropic
instances based on the ANTHROPIC_ZERO_RETENTION setting.
"""

from unittest.mock import patch

import pytest

from src.agent.llm import clear_llm_cache, get_llm
from src.config import Settings


@pytest.fixture
def _clear_cache():
    """Ensure LLM cache is cleared before and after each test."""
    clear_llm_cache()
    yield
    clear_llm_cache()


def _make_settings(*, zero_retention: bool) -> Settings:
    """Create test settings with the given zero-retention flag."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
        SECRET_KEY="test-secret",  # pragma: allowlist secret
        ANTHROPIC_ZERO_RETENTION=zero_retention,
    )


class TestZeroRetentionHeaders:
    """Tests for x-no-store header on ChatAnthropic instances."""

    @pytest.mark.usefixtures("_clear_cache")
    def test_no_extra_headers_when_disabled(self) -> None:
        """When ANTHROPIC_ZERO_RETENTION=False, no default_headers are set."""
        settings = _make_settings(zero_retention=False)
        with patch("src.config.get_settings", return_value=settings):
            llm = get_llm("default")

        # default_headers should be absent or not contain x-no-store
        headers = getattr(llm, "default_headers", None) or {}
        assert "x-no-store" not in headers

    @pytest.mark.usefixtures("_clear_cache")
    def test_x_no_store_header_when_enabled(self) -> None:
        """When ANTHROPIC_ZERO_RETENTION=True, x-no-store header is set."""
        settings = _make_settings(zero_retention=True)
        with patch("src.config.get_settings", return_value=settings):
            llm = get_llm("default")

        headers = getattr(llm, "default_headers", {})
        assert headers.get("x-no-store") == "true"

    @pytest.mark.usefixtures("_clear_cache")
    def test_cache_returns_same_instance(self) -> None:
        """Cached LLM instances are reused for the same profile."""
        settings = _make_settings(zero_retention=True)
        with patch("src.config.get_settings", return_value=settings):
            llm1 = get_llm("default")
            llm2 = get_llm("default")

        assert llm1 is llm2

    @pytest.mark.usefixtures("_clear_cache")
    def test_different_profiles_get_separate_instances(self) -> None:
        """Different profiles produce distinct cached instances."""
        settings = _make_settings(zero_retention=True)
        with patch("src.config.get_settings", return_value=settings):
            llm_default = get_llm("default")
            llm_analysis = get_llm("analysis")

        assert llm_default is not llm_analysis
        # Both should still carry the header
        assert getattr(llm_default, "default_headers", {}).get("x-no-store") == "true"
        assert getattr(llm_analysis, "default_headers", {}).get("x-no-store") == "true"
