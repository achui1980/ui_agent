from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel
from playwright.sync_api import Page


class GetValidationErrorsInput(BaseModel):
    """No parameters needed - scans page for validation errors."""
    pass


class GetValidationErrorsTool(BaseTool):
    name: str = "Get Validation Errors"
    description: str = (
        "Scan the current page for validation error messages. "
        "Returns a JSON list of errors with their associated field selectors."
    )
    args_schema: type[BaseModel] = GetValidationErrorsInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(self) -> str:
        try:
            result = self.page.evaluate("""() => {
                const errors = [];

                // Strategy 1: CSS class-based detection
                const errorSelectors = [
                    '.error', '.invalid', '.field-error',
                    '.validation-error', '.form-error',
                    '[class*="error"]', '[class*="invalid"]',
                    '[role="alert"]',
                ];
                document.querySelectorAll(errorSelectors.join(', '))
                    .forEach(el => {
                        const msg = el.textContent?.trim();
                        if (!msg || msg.length > 500) return;
                        // Try to find associated field
                        const field = el.closest('.form-group, .field-wrapper, .form-field');
                        const input = field
                            ? field.querySelector('input, select, textarea')
                            : null;
                        errors.push({
                            message: msg,
                            field_selector: input
                                ? (input.id ? '#' + input.id : '[name="' + input.name + '"]')
                                : null,
                            field_label: input
                                ? (document.querySelector('label[for="' + input.id + '"]')
                                    ?.textContent?.trim() || '')
                                : '',
                        });
                    });

                // Strategy 2: HTML5 validity
                document.querySelectorAll('input, select, textarea')
                    .forEach(el => {
                        if (!el.checkValidity()) {
                            errors.push({
                                message: el.validationMessage,
                                field_selector: el.id
                                    ? '#' + el.id
                                    : '[name="' + el.name + '"]',
                                field_label: '',
                            });
                        }
                    });

                // Deduplicate by message
                const seen = new Set();
                const unique = errors.filter(e => {
                    if (seen.has(e.message)) return false;
                    seen.add(e.message);
                    return true;
                });

                return JSON.stringify(unique);
            }""")
            return result
        except Exception as e:
            return f"FAILED: Could not extract validation errors: {e}"
