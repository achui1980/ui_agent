from __future__ import annotations

import json

from crewai import LLM
from loguru import logger

from src.config import Settings
from src.models import TestCase


def _build_field_description(fields: list[dict]) -> str:
    """Build a human-readable field description from DOM extractor output."""
    lines = []
    for i, f in enumerate(fields, 1):
        label = f.get("label", "").strip()
        field_type = f.get("type", "text")
        tag = f.get("tag", "input")
        required = f.get("required", False)
        options = f.get("options", [])
        enabled = f.get("enabled", True)
        field_id = f.get("id", "")
        group = f.get("group", "")

        if not label and not field_id:
            continue

        # Build a meaningful name: prefer label, then derive from ID
        if label:
            name = label
        elif field_id:
            # Convert IDs like "dateOfBirthInput" -> "Date of Birth"
            # and "react-select-3-input" -> use group or ID
            clean_id = field_id.replace("Input", "").replace("input", "")
            clean_id = clean_id.replace("react-select-", "dropdown-")
            # camelCase to spaces
            import re

            name = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean_id)
            name = name.replace("-", " ").replace("_", " ").strip()
            if group:
                name = f"{name} (group: {group})"
        else:
            name = "unknown"

        parts = [f'{i}. "{name}"']

        # Determine display type
        if tag == "select" or options:
            opt_texts = [o.get("text", o.get("value", "")) for o in options]
            parts.append(f"dropdown: {', '.join(opt_texts[:10])}")
        elif tag == "textarea":
            parts.append("textarea")
        elif field_type == "radio":
            parts.append(f"radio: {f.get('value', '')}")
        elif field_type == "checkbox":
            parts.append("checkbox")
        elif field_type == "file":
            parts.append("file upload")
        else:
            parts.append(f"{field_type} input")

        if required:
            parts.append("required")
        if not enabled:
            parts.append("disabled")

        lines.append(" - ".join(parts))

    return "\n".join(lines)


def parse_natural_language(
    path: str,
    url: str,
    settings: Settings,
    page_context: dict | None = None,
) -> list[TestCase]:
    """Parse a natural language description into TestCase using LLM.

    If page_context is provided (from DOM extraction), the LLM receives
    the target form's field list to produce more accurate extractions.
    page_context is required — callers must analyze the page first.
    """
    if page_context is None:
        raise ValueError(
            "Natural language parsing requires page context. "
            "Provide a URL so the system can analyze the target form first."
        )

    with open(path, encoding="utf-8") as f:
        text = f.read().strip()

    llm = LLM(
        model=settings.llm_model,
        base_url=settings.openai_api_base or None,
        api_key=settings.openai_api_key,
    )

    # Build field context from page analysis
    fields = page_context.get("fields", [])
    field_desc = _build_field_description(fields)

    prompt = f"""You are a test data extraction assistant. You are given:
1. A natural language description of form test data
2. The actual fields on the target web form

Your job is to extract structured key-value pairs from the description
that match the form fields.

=== TARGET FORM FIELDS ===
URL: {url}
{field_desc}

=== USER DESCRIPTION ===
{text}

=== INSTRUCTIONS ===
- Extract ONLY data that matches the form fields listed above.
- Use snake_case versions of the field labels as keys (e.g. "First Name" -> "first_name", "Date of Birth" -> "date_of_birth", "Mobile Number" -> "mobile").
- If a field has no label but has an ID like "dateOfBirthInput", derive a semantic key like "date_of_birth".
- If a field has an ID like "react-select-3-input" with a nearby group like "State and City", use "state" or "city" as the key.
- For radio/checkbox fields, use the exact option text from the field list.
- For dropdown fields, use the exact option text from the field list.
- Keep date values in their natural format as described in the text (e.g. "15 Jan 1990", "1990-01-15"). Do NOT convert dates to a specific format — the downstream agent will handle format conversion based on the target form.
- If a field has no matching data in the description, omit it.
- Return ONLY a valid JSON object, no other text.

Return this JSON structure:
{{
  "test_id": "a short identifier based on the description",
  "description": "brief summary of the test case",
  "expected_outcome": "success",
  "data": {{
    "field_key": "value"
  }}
}}"""

    logger.info(f"Parsing NL with page context ({len(fields)} fields)")
    response = llm.call([{"role": "user", "content": prompt}])
    response_text = str(response).strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        response_text = "\n".join(lines)

    parsed = json.loads(response_text)

    test_case = TestCase(
        test_id=parsed.get("test_id", "nl_1"),
        url=url,
        data={str(k): str(v) for k, v in parsed.get("data", {}).items()},
        description=parsed.get("description", ""),
        expected_outcome=parsed.get("expected_outcome", "success"),
    )
    logger.info(
        f"Parsed NL test case: {test_case.test_id} ({len(test_case.data)} fields)"
    )
    return [test_case]
