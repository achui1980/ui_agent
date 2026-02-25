from __future__ import annotations

import json
import os

from loguru import logger


def save_json_report(report: dict, test_case_id: str) -> str:
    """Save test report as JSON file."""
    os.makedirs("reports", exist_ok=True)
    path = f"reports/{test_case_id}_report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON report saved: {path}")
    return path
