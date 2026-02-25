from __future__ import annotations

import json

from crewai import LLM
from loguru import logger

from src.config import Settings
from src.models import TestCase


def parse_natural_language(path: str, url: str, settings: Settings) -> list[TestCase]:
    """Parse a natural language description into TestCase using LLM."""
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()

    llm = LLM(
        model=settings.llm_model,
        base_url=settings.openai_api_base or None,
        api_key=settings.openai_api_key,
    )

    prompt = f"""You are a test data extraction assistant. Given the following natural
language description of form test data, extract structured key-value pairs.

Input text:
---
{text}
---

Return ONLY a valid JSON object with this structure:
{{
  "test_id": "a short identifier",
  "description": "brief summary of the test case",
  "expected_outcome": "success or failure",
  "data": {{
    "field_name_1": "value_1",
    "field_name_2": "value_2"
  }}
}}

Use snake_case for field names. Convert dates to MM/DD/YYYY format.
Return ONLY the JSON, no other text."""

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
    logger.info(f"Parsed natural language test case: {test_case.test_id}")
    return [test_case]
