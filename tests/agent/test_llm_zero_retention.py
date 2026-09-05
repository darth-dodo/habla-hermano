"""Tests for LLM zero-retention (data-collection) configuration.

Verifies that the OpenRouter ``provider.data_collection="deny"`` policy is
conditionally applied to ChatOpenAI instances (via ``extra_body``) based on
the OPENROUTER_ZERO_RETENTION setting.
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
        OPENROUTER_API_KEY="test-key",  # pragma: allowlist secret
        SECRET_KEY="test-secret",  # pragma: allowlist secret
        OPENROUTER_ZERO_RETENTION=zero_retention,
    )


def _data_collection(llm: object) -> str | None:
    """Extract the OpenRouter data_collection policy from an LLM's extra_body."""
    extra_body = getattr(llm, "extra_body", None) or {}
    provider = extra_body.get("provider", {}) if isinstance(extra_body, dict) else {}
    return provider.get("data_collection")


class TestZeroRetentionDataCollection:
    """Tests for the provider.data_collection policy on ChatOpenAI instances."""

    @pytest.mark.usefixtures("_clear_cache")
    def test_no_data_policy_when_disabled(self) -> None:
        """When OPENROUTER_ZERO_RETENTION=False, no data_collection policy is set."""
        settings = _make_settings(zero_retention=False)
        with patch("src.config.get_settings", return_value=settings):
            llm = get_llm("default")

        assert _data_collection(llm) is None

    @pytest.mark.usefixtures("_clear_cache")
    def test_data_collection_deny_when_enabled(self) -> None:
        """When OPENROUTER_ZERO_RETENTION=True, data_collection is set to 'deny'."""
        settings = _make_settings(zero_retention=True)
        with patch("src.config.get_settings", return_value=settings):
            llm = get_llm("default")

        assert _data_collection(llm) == "deny"

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
        # Both should still carry the data_collection policy
        assert _data_collection(llm_default) == "deny"
        assert _data_collection(llm_analysis) == "deny"
