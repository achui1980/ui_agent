from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class FillInputInput(BaseModel):
    selector: str = Field(
        ..., description="CSS selector, e.g. #first_name or [name='email']"
    )
    value: str = Field(..., description="The value to fill in")


class FillInputTool(BaseTool):
    name: str = "Fill Input"
    description: str = (
        "Fill a text input field with a value. "
        "Works for text, email, phone, number, and similar input types."
    )
    args_schema: type[BaseModel] = FillInputInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, value: str) -> str:
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()
            locator.fill(value)
            # Dismiss any autocomplete/datepicker popups that may have appeared
            locator.press("Escape")
            self.page.wait_for_timeout(200)
            return f"SUCCESS: Filled '{selector}' with '{value}'"
        except Exception:
            # Self-healing: try press_sequentially
            try:
                locator = self.page.locator(selector)
                locator.click()
                locator.clear()
                locator.press_sequentially(value, delay=50)
                locator.press("Escape")
                self.page.wait_for_timeout(200)
                return f"HEALED: Filled '{selector}' with slow typing"
            except Exception as e2:
                return f"FAILED: Could not fill '{selector}': {e2}"
