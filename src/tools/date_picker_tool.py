from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class DatePickerInput(BaseModel):
    selector: str = Field(
        ..., description="CSS selector of the date input or date picker trigger"
    )
    value: str = Field(
        ...,
        description="Date value in YYYY-MM-DD or MM/DD/YYYY or 'DD Mon YYYY' format",
    )


class DatePickerTool(BaseTool):
    name: str = "Date Picker"
    description: str = (
        "Fill a date picker field. Handles both native date inputs and "
        "react-datepicker components. Tries triple-click-select then type, "
        "direct fill, and JS injection as fallbacks."
    )
    args_schema: type[BaseModel] = DatePickerInput
    page: Any = None
    collector: Any = None  # FieldResultCollector instance

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, value: str) -> str:
        # Strategy 1: Triple-click to select all, type value, press Escape
        # This works reliably with react-datepicker and similar calendar widgets
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()
            locator.click(click_count=3)
            self.page.wait_for_timeout(200)
            locator.press_sequentially(value, delay=50)
            self.page.wait_for_timeout(200)
            locator.press("Escape")
            self.page.wait_for_timeout(300)
            result = f"SUCCESS: Date filled '{selector}' with '{value}'"
            self._record_result(selector, value, result)
            return result
        except Exception:
            pass

        # Strategy 2: Direct fill (works for native date inputs)
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()
            locator.fill(value)
            result = f"HEALED: Date direct-filled '{selector}' with '{value}'"
            self._record_result(selector, value, result)
            return result
        except Exception:
            pass

        # Strategy 3: JS value injection + input/change events
        try:
            self.page.eval_on_selector(
                selector,
                """(el, val) => {
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeInputValueSetter.call(el, val);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('blur', {bubbles: true}));
                }""",
                value,
            )
            result = f"HEALED: Date set via JS on '{selector}' with '{value}'"
            self._record_result(selector, value, result)
            return result
        except Exception as e:
            result = f"FAILED: Could not set date on '{selector}': {e}"
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
