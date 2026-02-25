from __future__ import annotations

import yaml
from loguru import logger

from src.models import TestCase


def parse_yaml(path: str, url: str) -> list[TestCase]:
    """Parse a YAML file into TestCase list.

    Same structure expectations as JSON parser.
    """
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if isinstance(raw, dict):
        raw = [raw]

    test_cases: list[TestCase] = []
    for idx, item in enumerate(raw):
        if isinstance(item, dict) and "data" in item:
            test_cases.append(TestCase(
                test_id=item.get("test_id", f"yaml_{idx + 1}"),
                url=item.get("url", url),
                data={str(k): str(v) for k, v in item["data"].items()},
                description=item.get("description", ""),
                expected_outcome=item.get("expected_outcome", "success"),
            ))
        elif isinstance(item, dict):
            test_cases.append(TestCase(
                test_id=f"yaml_{idx + 1}",
                url=url,
                data={str(k): str(v) for k, v in item.items()},
            ))

    logger.info(f"Parsed {len(test_cases)} test cases from {path}")
    return test_cases
