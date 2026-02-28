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
    collector: Any = None  # FieldResultCollector instance

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, check: bool = True) -> str:
        value = str(check)
        try:
            # Dismiss any popups/overlays that might be blocking
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(200)

            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()

            if check:
                locator.check()
                result = f"SUCCESS: Checked '{selector}'"
                self._record_result(selector, value, result)
                return result
            else:
                locator.uncheck()
                result = f"SUCCESS: Unchecked '{selector}'"
                self._record_result(selector, value, result)
                return result
        except Exception:
            # Self-healing: try clicking the associated label instead
            try:
                label = self.page.locator(f"label[for='{selector.lstrip('#')}']")
                if label.count() > 0:
                    label.click()
                    result = f"HEALED: Clicked label for '{selector}'"
                    self._record_result(selector, value, result)
                    return result
            except Exception:
                pass
            # Fallback: direct click on the element
            try:
                locator = self.page.locator(selector)
                locator.click(force=True)
                result = f"HEALED: Force-clicked '{selector}' as checkbox fallback"
                self._record_result(selector, value, result)
                return result
            except Exception as e2:
                result = f"FAILED: Could not toggle '{selector}': {e2}"
                self._record_result(selector, value, result)
                return result

    def _record_result(self, selector: str, value: str, result: str) -> None:
        if not self.collector:
            return
        if "SUCCESS" in result:
            status = "success"
        elif "HEALED" in result:
            status = "healed"
        else:
            status = "failed"
        self.collector.record(
            field_id=selector,
            selector=selector,
            value=value,
            status=status,
            error_message="" if status != "failed" else result,
        )
