from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class CheckboxInput(BaseModel):
    selector: str = Field(
        ..., description="CSS selector of the checkbox or radio input"
    )
    check: bool = Field(
        default=True,
        description="True to check, False to uncheck. For radio, always True.",
    )


class CheckboxTool(BaseTool):
    name: str = "Checkbox Toggle"
    description: str = (
        "Check or uncheck a checkbox, or select a radio button. "
        "Set check=True to select, check=False to deselect."
    )
    args_schema: type[BaseModel] = CheckboxInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, check: bool = True) -> str:
        try:
            # Dismiss any popups/overlays that might be blocking
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(200)

            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()

            if check:
                locator.check()
                return f"SUCCESS: Checked '{selector}'"
            else:
                locator.uncheck()
                return f"SUCCESS: Unchecked '{selector}'"
        except Exception:
            # Self-healing: try clicking the associated label instead
            try:
                label = self.page.locator(f"label[for='{selector.lstrip('#')}']")
                if label.count() > 0:
                    label.click()
                    return f"HEALED: Clicked label for '{selector}'"
            except Exception:
                pass
            # Fallback: direct click on the element
            try:
                locator = self.page.locator(selector)
                locator.click(force=True)
                return f"HEALED: Force-clicked '{selector}' as checkbox fallback"
            except Exception as e2:
                return f"FAILED: Could not toggle '{selector}': {e2}"
