from __future__ import annotations

import base64
import os
import time
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class ScreenshotInput(BaseModel):
    save_path: str = Field(
        default="",
        description="Optional file path to save the screenshot. "
                    "If empty, a timestamped name is generated.",
    )


class ScreenshotTool(BaseTool):
    name: str = "Screenshot"
    description: str = (
        "Take a screenshot of the current browser page. "
        "Returns the file path where the screenshot was saved."
    )
    args_schema: type[BaseModel] = ScreenshotInput
    page: Any = None  # Playwright Page instance

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, save_path: str = "") -> str:
        try:
            if not save_path:
                os.makedirs("reports/screenshots", exist_ok=True)
                save_path = f"reports/screenshots/page_{int(time.time())}.png"

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            self.page.screenshot(path=save_path, full_page=True)
            return f"SUCCESS: Screenshot saved to {save_path}"
        except Exception as e:
            return f"FAILED: Could not take screenshot: {e}"
