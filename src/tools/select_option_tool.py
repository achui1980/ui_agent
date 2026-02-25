from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class SelectOptionInput(BaseModel):
    selector: str = Field(
        ...,
        description=(
            "CSS selector of the select element or its container. "
            "For react-select, use the wrapper div selector (e.g. '#state') "
            "or the inner input (e.g. '#react-select-3-input')."
        ),
    )
    label: str = Field(default="", description="Option display text (preferred)")
    value: str = Field(default="", description="Option value attribute (fallback)")


class SelectOptionTool(BaseTool):
    name: str = "Select Option"
    description: str = (
        "Select an option in a dropdown/select element. "
        "Works with native <select>, react-select, and similar custom "
        "dropdown components. Prefers matching by label text; "
        "falls back to value attribute."
    )
    args_schema: type[BaseModel] = SelectOptionInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, label: str = "", value: str = "") -> str:
        text = label or value
        if not text:
            return "FAILED: No label or value provided"

        # Strategy 1: native <select> element
        try:
            tag = self.page.eval_on_selector(selector, "el => el.tagName.toLowerCase()")
            if tag == "select":
                return self._select_native(selector, label, value)
        except Exception:
            pass

        # Strategy 2: react-select — click container, type to search, pick option
        try:
            result = self._select_react(selector, text)
            if result:
                return result
        except Exception:
            pass

        # Strategy 3: generic custom dropdown — click to open, then click matching option
        try:
            result = self._select_generic(selector, text)
            if result:
                return result
        except Exception as e:
            return f"FAILED: Could not select '{text}' in '{selector}': {e}"

        return f"FAILED: Could not select '{text}' in '{selector}'"

    def _select_native(self, selector: str, label: str, value: str) -> str:
        """Handle native <select> elements."""
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed()
            if label:
                self.page.select_option(selector, label=label)
                return f"SUCCESS: Selected label='{label}' in '{selector}'"
            elif value:
                self.page.select_option(selector, value=value)
                return f"SUCCESS: Selected value='{value}' in '{selector}'"
        except Exception:
            # Fuzzy match fallback
            try:
                target = label or value
                options = self.page.locator(f"{selector} option").all()
                for opt in options:
                    text = opt.text_content().strip()
                    if target.lower() in text.lower():
                        val = opt.get_attribute("value")
                        self.page.select_option(selector, value=val)
                        return (
                            f"HEALED: Fuzzy-matched '{target}' -> '{text}' "
                            f"in '{selector}'"
                        )
            except Exception:
                pass
        return ""

    def _select_react(self, selector: str, text: str) -> str:
        """Handle react-select components.

        react-select structure:
        - Container div with class containing 'react-select' or css__control
        - Hidden <input> with id like 'react-select-N-input'
        - Options rendered in a menu portal or sibling div
        """
        # Find the react-select input element
        input_locator = None

        # If selector points directly to the react-select input
        if "react-select" in selector:
            input_locator = self.page.locator(selector)
        else:
            # Try to find react-select input inside or near the selector
            input_locator = self.page.locator(f"{selector} input[id*='react-select']")
            if input_locator.count() == 0:
                # Maybe selector IS the container — look for the control div
                input_locator = self.page.locator(f"{selector} input[role='combobox']")
            if input_locator.count() == 0:
                return ""

        try:
            # Click the container area to open the dropdown
            container = input_locator.locator("..")
            container.click()
            self.page.wait_for_timeout(300)

            # Type search text to filter options
            input_locator.fill(text)
            self.page.wait_for_timeout(500)

            # Find and click the matching option (preferred over Enter)
            option = self.page.locator(f"[class*='option']:has-text('{text}')").first
            try:
                option.wait_for(state="visible", timeout=3000)
                option.click()
                self.page.wait_for_timeout(500)
                return f"SUCCESS: react-select '{text}' in '{selector}'"
            except Exception:
                # Fallback: press Enter to select first filtered option
                input_locator.press("Enter")
                self.page.wait_for_timeout(500)
                return f"HEALED: react-select Enter-confirmed '{text}' in '{selector}'"
        except Exception:
            # Last resort: type + Enter
            try:
                input_locator.fill(text)
                self.page.wait_for_timeout(500)
                input_locator.press("Enter")
                self.page.wait_for_timeout(500)
                return f"HEALED: react-select typed+Enter '{text}' in '{selector}'"
            except Exception:
                return ""

        try:
            # Click the container area to open the dropdown
            container = input_locator.locator("..")
            container.click()
            self.page.wait_for_timeout(300)

            # Type search text to filter options
            input_locator.fill(text)
            self.page.wait_for_timeout(500)

            # Find and click the matching option
            option = self.page.locator(f"[class*='option']:has-text('{text}')").first
            if option.is_visible():
                option.click()
                self.page.wait_for_timeout(300)
                return f"SUCCESS: react-select '{text}' in '{selector}'"

            # Fallback: press Enter to select first filtered option
            input_locator.press("Enter")
            self.page.wait_for_timeout(300)
            return f"HEALED: react-select Enter-confirmed '{text}' in '{selector}'"
        except Exception:
            # Last resort: type + Enter
            try:
                input_locator.fill(text)
                self.page.wait_for_timeout(500)
                input_locator.press("Enter")
                self.page.wait_for_timeout(300)
                return f"HEALED: react-select typed+Enter '{text}' in '{selector}'"
            except Exception:
                return ""

    def _select_generic(self, selector: str, text: str) -> str:
        """Handle generic custom dropdown (click to open, click option)."""
        try:
            trigger = self.page.locator(selector)
            trigger.wait_for(state="visible", timeout=10000)
            trigger.scroll_into_view_if_needed()
            trigger.click()
            self.page.wait_for_timeout(500)

            # Look for a visible option matching the text
            option = self.page.locator(
                f"[role='option']:has-text('{text}'), "
                f"[role='listbox'] >> text='{text}', "
                f"li:has-text('{text}')"
            ).first
            option.wait_for(state="visible", timeout=5000)
            option.click()
            self.page.wait_for_timeout(300)
            return f"HEALED: Generic dropdown selected '{text}' in '{selector}'"
        except Exception:
            return ""
