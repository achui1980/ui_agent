from __future__ import annotations

import json
from loguru import logger

from src.models import TestCase


def parse_json(path: str, url: str) -> list[TestCase]:
    """Parse a JSON file into TestCase list.

    Supports two formats:
    1. A list of objects, each with at least a 'data' dict
    2. A single object with a 'data' dict (one test case)
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        raw = [raw]

    test_cases: list[TestCase] = []
    for idx, item in enumerate(raw):
        if isinstance(item, dict) and "data" in item:
            test_cases.append(TestCase(
                test_id=item.get("test_id", f"json_{idx + 1}"),
                url=item.get("url", url),
                data={str(k): str(v) for k, v in item["data"].items()},
                description=item.get("description", ""),
                expected_outcome=item.get("expected_outcome", "success"),
            ))
        elif isinstance(item, dict):
            # Treat the whole object as flat field->value data
            test_cases.append(TestCase(
                test_id=f"json_{idx + 1}",
                url=url,
                data={str(k): str(v) for k, v in item.items()},
            ))
        else:
            logger.warning(f"Skipping non-object item at index {idx}")

    logger.info(f"Parsed {len(test_cases)} test cases from {path}")
    return test_cases
