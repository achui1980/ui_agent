from __future__ import annotations

import csv
from loguru import logger

from src.models import TestCase


def parse_csv(path: str, url: str) -> list[TestCase]:
    """Parse a CSV file into TestCase list.

    Same format as Excel: first row = headers, subsequent rows = test cases.
    """
    meta_keys = {"test_id", "url", "description", "expected_outcome"}
    test_cases: list[TestCase] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            meta: dict[str, str] = {}
            data: dict[str, str] = {}
            for key, val in row.items():
                if not key:
                    continue
                key = key.strip()
                str_val = val.strip() if val else ""
                if not str_val:
                    continue
                if key in meta_keys:
                    meta[key] = str_val
                else:
                    data[key] = str_val

            if not data:
                logger.warning(f"Row {row_idx} has no data fields, skipping")
                continue

            test_cases.append(TestCase(
                test_id=meta.get("test_id", f"csv_row_{row_idx}"),
                url=meta.get("url", url),
                data=data,
                description=meta.get("description", ""),
                expected_outcome=meta.get("expected_outcome", "success"),
            ))

    logger.info(f"Parsed {len(test_cases)} test cases from {path}")
    return test_cases
