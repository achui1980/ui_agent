"""Tests for configuration."""

from __future__ import annotations

from src.config import Settings, get_settings


class TestSettings:
    def test_defaults(self):
        s = Settings(openai_api_key="test")
        assert s.browser_headless is False
        assert s.awa_max_steps == 50
        assert s.log_level == "INFO"

    def test_override(self):
        s = Settings(openai_api_key="test", browser_headless=True, log_level="DEBUG")
        assert s.browser_headless is True
        assert s.log_level == "DEBUG"

    def test_get_settings_returns_instance(self):
        s = get_settings()
        assert isinstance(s, Settings)
