from __future__ import annotations

import base64
import os
import time
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page
from loguru import logger


class ScreenshotAnalysisInput(BaseModel):
    question: str = Field(
        default="Describe all form fields, buttons, dropdowns, date pickers, "
        "and any error messages visible on this page. "
        "For each element, describe its type, label, and position.",
        description=(
            "The question to ask the vision model about the screenshot. "
            "Defaults to a comprehensive form analysis prompt."
        ),
    )


class ScreenshotAnalysisTool(BaseTool):
    name: str = "Screenshot Analysis"
    description: str = (
        "Take a screenshot of the current browser page and analyze it "
        "using a vision language model (VLM). Returns a detailed visual "
        "description of the page layout, form fields, buttons, dropdowns, "
        "custom components (like date pickers and react-select), "
        "error messages, and other UI elements that may not be fully "
        "captured by DOM extraction alone."
    )
    args_schema: type[BaseModel] = ScreenshotAnalysisInput
    page: Any = None
    vlm_model: str = ""
    vlm_api_key: str = ""
    vlm_api_base: str = ""
    vlm_max_tokens: int = 1000

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, question: str = "") -> str:
        if not question:
            question = (
                "Describe all form fields, buttons, dropdowns, date pickers, "
                "and any error messages visible on this page. "
                "For each element, describe its type, label, and position."
            )

        # Step 1: Take screenshot and encode as base64
        try:
            os.makedirs("reports/screenshots", exist_ok=True)
            save_path = f"reports/screenshots/analysis_{int(time.time())}.png"
            self.page.screenshot(path=save_path, full_page=True)
            logger.info(f"Screenshot saved for analysis: {save_path}")

            with open(save_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return f"FAILED: Could not take screenshot: {e}"

        # Step 2: Call VLM with the screenshot
        try:
            from openai import OpenAI

            client_kwargs: dict[str, Any] = {"api_key": self.vlm_api_key}
            if self.vlm_api_base:
                client_kwargs["base_url"] = self.vlm_api_base

            client = OpenAI(**client_kwargs)

            response = client.chat.completions.create(
                model=self.vlm_model,
                max_completion_tokens=self.vlm_max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are analyzing a web page screenshot for "
                                    "automated form testing. " + question + "\n\n"
                                    "Pay special attention to:\n"
                                    "- Custom dropdown components (react-select, "
                                    "autocomplete) that look like text inputs "
                                    "with a chevron/arrow\n"
                                    "- Date picker fields that open calendar popups\n"
                                    "- Radio buttons and checkboxes with their labels\n"
                                    "- Multi-step form indicators (step 1 of N)\n"
                                    "- Submit/Next buttons and their position\n"
                                    "- Any validation error messages\n"
                                    "- Field groupings and visual hierarchy\n"
                                    "- File upload areas\n\n"
                                    "Return a structured description."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                },
                            },
                        ],
                    }
                ],
            )

            analysis = response.choices[0].message.content or ""
            logger.info(f"VLM analysis complete ({len(analysis)} chars)")
            return f"SUCCESS: Visual analysis of {save_path}:\n\n{analysis}"

        except Exception as e:
            logger.warning(f"VLM analysis failed: {e}")
            return (
                f"HEALED: Screenshot saved to {save_path} but VLM analysis "
                f"failed: {e}. Rely on DOM Extractor results instead."
            )
