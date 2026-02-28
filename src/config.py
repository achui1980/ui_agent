from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    # LLM
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_api_base: str = Field(default="")
    https_proxy: str = Field(default="")
    llm_model: str = Field(default="gpt-5.2")
    vlm_model: str = Field(default="gpt-5.2")
    llm_max_tokens: int = Field(default=4096)
    vlm_max_tokens: int = Field(default=1000)

    # Browser
    browser_headless: bool = Field(default=False)
    browser_timeout: int = Field(default=10000)
    browser_navigation_timeout: int = Field(default=60000)
    browser_viewport_width: int = Field(default=1280)
    browser_viewport_height: int = Field(default=720)
    browser_proxy: str = Field(default="")

    # AWA
    awa_max_steps: int = Field(default=50)
    awa_max_healing_attempts: int = Field(default=3)
    awa_screenshot_dir: str = Field(default="reports/screenshots")

    # Logging
    log_level: str = Field(default="INFO")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
