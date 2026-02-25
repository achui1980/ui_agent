from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class ClickButtonInput(BaseModel):
    selector: str = Field(..., description="CSS selector of the button")
    wait_for_navigation: bool = Field(
        default=True,
        description="Whether to wait for page load after clicking",
    )


class ClickButtonTool(BaseTool):
    name: str = "Click Button"
    description: str = (
        "Click a button on the page (submit, next step, etc.). "
        "Optionally waits for navigation/network idle after clicking."
    )
    args_schema: type[BaseModel] = ClickButtonInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(
        self, selector: str, wait_for_navigation: bool = True
    ) -> str:
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()
            locator.click()
            if wait_for_navigation:
                self.page.wait_for_load_state("networkidle", timeout=30000)
            return f"SUCCESS: Clicked '{selector}'"
        except Exception:
            # Self-healing: try JavaScript click
            try:
                self.page.eval_on_selector(
                    selector, "el => el.click()"
                )
                if wait_for_navigation:
                    self.page.wait_for_load_state(
                        "networkidle", timeout=30000
                    )
                return f"HEALED: JS-clicked '{selector}'"
            except Exception as e2:
                return f"FAILED: Could not click '{selector}': {e2}"
