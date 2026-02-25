"""Shared pytest fixtures for UI Agent tests."""
from __future__ import annotations

import os
import pytest

from src.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Return a test Settings instance with defaults."""
    return Settings(
        openai_api_key="test-key",
        openai_api_base="",
        llm_model="gpt-5.2",
        browser_headless=True,
        browser_timeout=10000,
        browser_navigation_timeout=15000,
        browser_viewport_width=1280,
        browser_viewport_height=720,
        browser_proxy="",
        log_level="DEBUG",
    )


@pytest.fixture
def sample_test_data() -> dict[str, str]:
    """Return sample test case data."""
    return {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "date_of_birth": "01/15/1990",
        "gender": "Male",
        "state": "Illinois",
    }


@pytest.fixture
def test_data_dir() -> str:
    """Return path to test_data directory."""
    return os.path.join(os.path.dirname(__file__), "..", "test_data")
