from __future__ import annotations

import os

from loguru import logger

from src.config import Settings
from src.models import TestCase
from .excel_parser import parse_excel
from .csv_parser import parse_csv
from .json_parser import parse_json
from .yaml_parser import parse_yaml
from .nl_parser import parse_natural_language


def parse_test_file(
    path: str, url: str, settings: Settings | None = None
) -> list[TestCase]:
    """Dispatch to the appropriate parser based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    logger.info(f"Parsing test file: {path} (extension: {ext})")

    if ext in (".xlsx", ".xls"):
        return parse_excel(path, url)
    elif ext == ".csv":
        return parse_csv(path, url)
    elif ext == ".json":
        return parse_json(path, url)
    elif ext in (".yaml", ".yml"):
        return parse_yaml(path, url)
    elif ext == ".txt":
        if settings is None:
            raise ValueError(
                "Settings required for natural language parsing"
            )
        return parse_natural_language(path, url, settings)
    else:
        raise ValueError(f"Unsupported test file format: {ext}")
