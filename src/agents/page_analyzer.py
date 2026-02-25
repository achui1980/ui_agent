from __future__ import annotations

from crewai import Agent, LLM
from playwright.sync_api import Page

from src.config import Settings
from src.tools.screenshot_tool import ScreenshotTool
from src.tools.dom_extractor_tool import DOMExtractorTool
from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool


def create_page_analyzer(
    page: Page, llm: LLM, settings: Settings | None = None
) -> Agent:
    tools = [
        DOMExtractorTool(page=page),
        ScreenshotTool(page=page),
    ]

    # Add VLM-powered screenshot analysis if settings are available
    if settings and settings.vlm_model:
        tools.append(
            ScreenshotAnalysisTool(
                page=page,
                vlm_model=settings.vlm_model,
                vlm_api_key=settings.openai_api_key,
                vlm_api_base=settings.openai_api_base,
                vlm_max_tokens=settings.vlm_max_tokens,
            )
        )

    return Agent(
        role="Page Analyzer",
        goal=(
            "Analyze the current form page: extract all form fields with precise "
            "CSS selectors, labels, types, and options. Identify navigation buttons "
            "and any existing validation errors. Use BOTH DOM extraction and visual "
            "screenshot analysis to get the most accurate picture — DOM extraction "
            "provides precise selectors while visual analysis helps identify custom "
            "components like react-select dropdowns and date pickers."
        ),
        backstory=(
            "You are a senior front-end test engineer specializing in complex "
            "insurance and financial application forms. You understand multi-step "
            "wizards, conditional fields, and nested form groups. You combine DOM "
            "data with visual analysis to accurately identify custom UI components "
            "that might not be obvious from DOM structure alone."
        ),
        tools=tools,
        llm=llm,
        verbose=True,
    )
