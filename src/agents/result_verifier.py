from __future__ import annotations

from crewai import Agent, LLM
from playwright.sync_api import Page

from src.config import Settings
from src.tools.screenshot_tool import ScreenshotTool
from src.tools.validation_error_tool import GetValidationErrorsTool


def create_result_verifier(
    page: Page, llm: LLM, settings: Settings | None = None
) -> Agent:
    screenshot_dir = settings.awa_screenshot_dir if settings else "reports/screenshots"
    return Agent(
        role="Result Verifier",
        goal=(
            "Verify the form submission result. Detect validation errors, "
            "confirm successful page transitions, and identify completion pages "
            "with confirmation numbers or success messages."
        ),
        backstory=(
            "You are a meticulous QA verification expert who can accurately "
            "detect error states, success indicators, and page transitions from "
            "both DOM content and visual screenshots."
        ),
        tools=[
            ScreenshotTool(page=page, screenshot_dir=screenshot_dir),
            GetValidationErrorsTool(page=page),
        ],
        llm=llm,
        verbose=True,
    )
