from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel
from playwright.sync_api import Page


class DOMExtractorInput(BaseModel):
    """No parameters needed - extracts all form elements from the current page."""
    pass


class DOMExtractorTool(BaseTool):
    name: str = "DOM Extractor"
    description: str = (
        "Extract all form elements from the current page, including their "
        "selectors, types, labels, options, and visibility status. "
        "Also detects submit/next buttons."
    )
    args_schema: type[BaseModel] = DOMExtractorInput
    page: Any = None  # Playwright Page instance

    model_config = {"arbitrary_types_allowed": True}

    def _run(self) -> str:
        try:
            result = self.page.evaluate("""() => {
                const fields = [];
                const seen = new Set();
                document.querySelectorAll(
                    'input, select, textarea, [role="combobox"], [role="listbox"]'
                ).forEach((el) => {
                    const key = el.id || el.name || '';
                    if (key && seen.has(key)) return;
                    if (key) seen.add(key);

                    const label = el.id
                        ? document.querySelector(`label[for="${el.id}"]`)
                        : null;
                    const parentLabel = el.closest('label');

                    // Try to find group/fieldset legend
                    const fieldset = el.closest('fieldset');
                    const legend = fieldset
                        ? fieldset.querySelector('legend')
                        : null;

                    fields.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        id: el.id || '',
                        name: el.name || '',
                        selector: el.id
                            ? '#' + el.id
                            : el.name
                                ? '[name="' + el.name + '"]'
                                : null,
                        label: (
                            label?.textContent?.trim()
                            || parentLabel?.textContent?.trim()
                            || el.getAttribute('aria-label')
                            || el.placeholder
                            || ''
                        ),
                        required:
                            el.required
                            || el.getAttribute('aria-required') === 'true',
                        visible: el.offsetParent !== null,
                        enabled: !el.disabled,
                        value: el.value || '',
                        options: el.tagName === 'SELECT'
                            ? Array.from(el.options).map(o => ({
                                text: o.text.trim(),
                                value: o.value,
                              }))
                            : [],
                        group: legend?.textContent?.trim() || '',
                    });
                });

                // Detect submit / next buttons
                const buttons = [];
                document.querySelectorAll(
                    'button, input[type="submit"], [role="button"], a.btn'
                ).forEach(btn => {
                    const text = (
                        btn.textContent?.trim() || btn.value || ''
                    );
                    if (!text) return;
                    buttons.push({
                        text: text,
                        selector: btn.id
                            ? '#' + btn.id
                            : null,
                        type: btn.type || 'button',
                        tag: btn.tagName.toLowerCase(),
                    });
                });

                // Detect step indicator
                let stepIndicator = '';
                const stepEl = document.querySelector(
                    '[class*="step"], [class*="progress"], [class*="wizard"]'
                );
                if (stepEl) {
                    stepIndicator = stepEl.textContent?.trim()?.substring(0, 100) || '';
                }

                // Detect existing validation errors
                const errors = [];
                document.querySelectorAll(
                    '.error, .invalid, [class*="error"], [class*="invalid"], '
                    + '[role="alert"], .field-error, .validation-error'
                ).forEach(errEl => {
                    const msg = errEl.textContent?.trim();
                    if (msg) errors.push(msg);
                });

                return JSON.stringify({
                    fields: fields,
                    buttons: buttons,
                    step_indicator: stepIndicator,
                    existing_errors: errors,
                    page_title: document.title,
                    url: window.location.href,
                });
            }""")
            return result
        except Exception as e:
            return f"FAILED: Could not extract DOM elements: {e}"
