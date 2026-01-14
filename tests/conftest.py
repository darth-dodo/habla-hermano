"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_message() -> str:
    """Sample user message for testing."""
    return "Hola, me llamo Juan"
