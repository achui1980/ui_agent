"""Tests for configuration and security."""

from __future__ import annotations

from pydantic import SecretStr

from src.config import Settings, get_settings
from src.utils.logging import sanitize_pii


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


class TestSecretStr:
    """NFR-01: API key must not leak via repr/str/model_dump."""

    def test_api_key_is_secret_str(self):
        s = Settings(openai_api_key="sk-test-key-1234567890")
        assert isinstance(s.openai_api_key, SecretStr)

    def test_api_key_hidden_in_repr(self):
        s = Settings(openai_api_key="sk-test-key-1234567890")
        assert "sk-test-key-1234567890" not in repr(s)

    def test_api_key_hidden_in_model_dump(self):
        s = Settings(openai_api_key="sk-test-key-1234567890")
        dumped = s.model_dump()
        # SecretStr dumps as '**********' by default
        assert dumped["openai_api_key"] != "sk-test-key-1234567890"

    def test_api_key_accessible_via_get_secret_value(self):
        s = Settings(openai_api_key="sk-test-key-1234567890")
        assert s.openai_api_key.get_secret_value() == "sk-test-key-1234567890"


class TestVlmApiKeyExcluded:
    """NFR-01: vlm_api_key must not appear in serialization."""

    def test_vlm_api_key_excluded_from_dump(self):
        from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

        tool = ScreenshotAnalysisTool(vlm_api_key="sk-secret-vlm-key")
        dumped = tool.model_dump()
        assert "vlm_api_key" not in dumped

    def test_vlm_api_key_hidden_in_repr(self):
        from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

        tool = ScreenshotAnalysisTool(vlm_api_key="sk-secret-vlm-key")
        assert "sk-secret-vlm-key" not in repr(tool)


class TestPiiSanitization:
    """NFR-02: PII patterns must be redacted in INFO+ log messages."""

    def test_redacts_ssn(self):
        msg = "Filled field with 123-45-6789"
        assert "123-45-6789" not in sanitize_pii(msg)
        assert "[SSN-REDACTED]" in sanitize_pii(msg)

    def test_redacts_email(self):
        msg = "User email is john.doe@example.com"
        assert "john.doe@example.com" not in sanitize_pii(msg)
        assert "[EMAIL-REDACTED]" in sanitize_pii(msg)

    def test_redacts_api_key(self):
        msg = "Using key sk-abcdefghijklmnopqrstuvwxyz1234567890"
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in sanitize_pii(msg)
        assert "[APIKEY-REDACTED]" in sanitize_pii(msg)

    def test_redacts_phone(self):
        msg = "Phone: (555) 123-4567"
        assert "(555) 123-4567" not in sanitize_pii(msg)
        assert "[PHONE-REDACTED]" in sanitize_pii(msg)

    def test_redacts_credit_card(self):
        msg = "Card: 4111-1111-1111-1111"
        assert "4111-1111-1111-1111" not in sanitize_pii(msg)
        assert "[CC-REDACTED]" in sanitize_pii(msg)

    def test_preserves_non_sensitive(self):
        msg = "SUCCESS: Filled '#first_name' field"
        assert sanitize_pii(msg) == msg

    def test_multiple_patterns_in_one_message(self):
        msg = "Filled SSN 123-45-6789 and email john@test.com"
        result = sanitize_pii(msg)
        assert "123-45-6789" not in result
        assert "john@test.com" not in result
        assert "[SSN-REDACTED]" in result
        assert "[EMAIL-REDACTED]" in result
