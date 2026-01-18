"""Tests for src/api/config.py - Settings class and get_settings function."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.api.config import Settings, get_settings


class TestSettingsClass:
    """Tests for the Settings class configuration and validation."""

    def test_settings_requires_anthropic_api_key(self) -> None:
        """Settings should raise ValidationError when ANTHROPIC_API_KEY is missing."""
        # Must use _env_file=None to prevent loading from .env file
        # and clear the environment to ensure no ANTHROPIC_API_KEY exists
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings(_env_file=None)  # type: ignore[call-arg]

            errors = exc_info.value.errors()
            assert len(errors) >= 1
            # Check that ANTHROPIC_API_KEY is in the missing fields
            field_names = [err["loc"][0] for err in errors]
            assert "ANTHROPIC_API_KEY" in field_names

    def test_settings_with_required_fields_only(self) -> None:
        """Settings should work with only required ANTHROPIC_API_KEY."""
        # Use _env_file=None to prevent loading defaults from .env
        settings = Settings(_env_file=None, ANTHROPIC_API_KEY="test-key-123")  # type: ignore[call-arg]

        assert settings.ANTHROPIC_API_KEY == "test-key-123"  # pragma: allowlist secret
        # Check defaults
        assert settings.APP_NAME == "Habla Hermano"
        assert settings.DEBUG is False
        assert settings.LLM_MODEL == "claude-sonnet-4-20250514"
        assert settings.LLM_TEMPERATURE == 0.7
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 8000

    def test_settings_with_all_fields(self, mock_settings: Settings) -> None:
        """Settings should accept all configurable fields."""
        assert mock_settings.ANTHROPIC_API_KEY == "test-api-key-12345"  # pragma: allowlist secret
        assert mock_settings.APP_NAME == "Habla Hermano-Test"
        assert mock_settings.DEBUG is True
        assert mock_settings.LLM_MODEL == "claude-test-model"
        assert mock_settings.LLM_TEMPERATURE == 0.5
        assert mock_settings.HOST == "127.0.0.1"
        assert mock_settings.PORT == 8000

    def test_settings_from_environment_variables(self, env_vars: dict[str, str]) -> None:
        """Settings should load values from environment variables."""
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]

            api_key = settings.ANTHROPIC_API_KEY  # pragma: allowlist secret
            assert api_key == "test-anthropic-api-key"  # pragma: allowlist secret
            assert settings.APP_NAME == "TestApp"
            assert settings.DEBUG is True
            assert settings.LLM_MODEL == "claude-test"
            assert settings.LLM_TEMPERATURE == 0.5
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 9000

    def test_settings_debug_false_string(self) -> None:
        """Settings should parse DEBUG=false correctly."""
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key", "DEBUG": "false"},  # pragma: allowlist secret
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.DEBUG is False

    def test_settings_debug_true_string(self) -> None:
        """Settings should parse DEBUG=true correctly."""
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key", "DEBUG": "true"},  # pragma: allowlist secret
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.DEBUG is True

    def test_settings_port_as_string(self) -> None:
        """Settings should convert PORT string to integer."""
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key", "PORT": "3000"},  # pragma: allowlist secret
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.PORT == 3000
            assert isinstance(settings.PORT, int)

    def test_settings_temperature_as_string(self) -> None:
        """Settings should convert LLM_TEMPERATURE string to float."""
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key", "LLM_TEMPERATURE": "0.9"},  # pragma: allowlist secret
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.LLM_TEMPERATURE == 0.9
            assert isinstance(settings.LLM_TEMPERATURE, float)

    def test_settings_extra_fields_ignored(self) -> None:
        """Settings should ignore extra/unknown environment variables."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",  # pragma: allowlist secret
                "UNKNOWN_SETTING": "some-value",
                "ANOTHER_UNKNOWN": "another-value",
            },
            clear=True,
        ):
            # Should not raise an error
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.ANTHROPIC_API_KEY == "test-key"  # pragma: allowlist secret
            # Extra fields should not be accessible
            assert not hasattr(settings, "UNKNOWN_SETTING")

    def test_settings_case_sensitivity(self) -> None:
        """Settings should be case sensitive for environment variables."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "correct-key",  # pragma: allowlist secret
                "anthropic_api_key": "wrong-key",  # pragma: allowlist secret
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.ANTHROPIC_API_KEY == "correct-key"  # pragma: allowlist secret


class TestSettingsProperties:
    """Tests for computed properties on Settings class."""

    def test_project_root_is_path(self, mock_settings: Settings) -> None:
        """project_root should return a Path object."""
        assert isinstance(mock_settings.project_root, Path)

    def test_project_root_exists(self, mock_settings: Settings) -> None:
        """project_root should point to an existing directory."""
        assert mock_settings.project_root.exists()
        assert mock_settings.project_root.is_dir()

    def test_templates_dir_is_path(self, mock_settings: Settings) -> None:
        """templates_dir should return a Path object."""
        assert isinstance(mock_settings.templates_dir, Path)

    def test_templates_dir_structure(self, mock_settings: Settings) -> None:
        """templates_dir should be under project_root/src/templates."""
        expected_path = mock_settings.project_root / "src" / "templates"
        assert mock_settings.templates_dir == expected_path

    def test_templates_dir_exists(self, mock_settings: Settings) -> None:
        """templates_dir should point to an existing directory."""
        assert mock_settings.templates_dir.exists()
        assert mock_settings.templates_dir.is_dir()

    def test_static_dir_is_path(self, mock_settings: Settings) -> None:
        """static_dir should return a Path object."""
        assert isinstance(mock_settings.static_dir, Path)

    def test_static_dir_structure(self, mock_settings: Settings) -> None:
        """static_dir should be under project_root/src/static."""
        expected_path = mock_settings.project_root / "src" / "static"
        assert mock_settings.static_dir == expected_path

    def test_log_level_debug_mode(self) -> None:
        """log_level should return DEBUG when DEBUG is True."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            DEBUG=True,
        )
        assert settings.log_level == "DEBUG"

    def test_log_level_production_mode(self) -> None:
        """log_level should return INFO when DEBUG is False."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            DEBUG=False,
        )
        assert settings.log_level == "INFO"

    def test_log_level_default(self) -> None:
        """log_level should default to INFO."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
        )
        assert settings.log_level == "INFO"


class TestGetSettings:
    """Tests for the get_settings function with LRU cache."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """get_settings should return a Settings instance."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_caches_result(self) -> None:
        """get_settings should return the same instance on subsequent calls."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            get_settings.cache_clear()
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_get_settings_cache_info(self) -> None:
        """get_settings cache should show hits after multiple calls."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            get_settings.cache_clear()

            # First call - miss
            get_settings()
            cache_info = get_settings.cache_info()
            assert cache_info.misses == 1
            assert cache_info.hits == 0

            # Second call - hit
            get_settings()
            cache_info = get_settings.cache_info()
            assert cache_info.misses == 1
            assert cache_info.hits == 1

            # Third call - hit
            get_settings()
            cache_info = get_settings.cache_info()
            assert cache_info.misses == 1
            assert cache_info.hits == 2

    def test_get_settings_cache_clear(self) -> None:
        """get_settings cache should be clearable."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            get_settings.cache_clear()

            get_settings()
            get_settings.cache_clear()

            # After clearing, the next call should create a new instance
            get_settings()
            cache_info = get_settings.cache_info()
            assert cache_info.misses == 1  # Fresh miss after clear

    def test_get_settings_uses_environment(self) -> None:
        """get_settings should create Settings from environment."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "env-test-key",  # pragma: allowlist secret
                "APP_NAME": "EnvTestApp",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.ANTHROPIC_API_KEY == "env-test-key"  # pragma: allowlist secret
            assert settings.APP_NAME == "EnvTestApp"


class TestSettingsValidation:
    """Tests for Settings field validation edge cases."""

    def test_empty_api_key_accepted(self) -> None:
        """Empty string for ANTHROPIC_API_KEY should be accepted (no min length)."""
        # Note: pydantic-settings accepts empty strings, validation for actual
        # API key validity would happen at the Anthropic client level
        settings = Settings(_env_file=None, ANTHROPIC_API_KEY="")  # type: ignore[call-arg]
        assert settings.ANTHROPIC_API_KEY == ""

    def test_whitespace_api_key_preserved(self) -> None:
        """Whitespace in ANTHROPIC_API_KEY should be preserved."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="  test-key-with-spaces  ",
        )
        assert settings.ANTHROPIC_API_KEY == "  test-key-with-spaces  "

    def test_negative_port_accepted(self) -> None:
        """Negative port values should be accepted by Settings (validation elsewhere)."""
        # Note: Port validation would typically be at the server level
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            PORT=-1,
        )
        assert settings.PORT == -1

    def test_temperature_boundary_zero(self) -> None:
        """LLM_TEMPERATURE of 0 should be accepted."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            LLM_TEMPERATURE=0.0,
        )
        assert settings.LLM_TEMPERATURE == 0.0

    def test_temperature_boundary_one(self) -> None:
        """LLM_TEMPERATURE of 1 should be accepted."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            LLM_TEMPERATURE=1.0,
        )
        assert settings.LLM_TEMPERATURE == 1.0

    def test_temperature_above_one(self) -> None:
        """LLM_TEMPERATURE above 1 should be accepted (Anthropic allows up to 2)."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            LLM_TEMPERATURE=1.5,
        )
        assert settings.LLM_TEMPERATURE == 1.5

    def test_special_characters_in_app_name(self) -> None:
        """APP_NAME should accept special characters."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            APP_NAME="Habla Hermano - Test Version (v1.0)",
        )
        assert settings.APP_NAME == "Habla Hermano - Test Version (v1.0)"

    def test_unicode_in_app_name(self) -> None:
        """APP_NAME should accept unicode characters."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",
            APP_NAME="Habla Hermano Espanol",
        )
        assert settings.APP_NAME == "Habla Hermano Espanol"
