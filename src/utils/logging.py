from __future__ import annotations

import re
import sys

from loguru import logger

from src.config import get_settings


# PII patterns to redact in INFO+ log messages
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # SSN: 123-45-6789
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN-REDACTED]"),
    # Email addresses
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL-REDACTED]",
    ),
    # OpenAI API keys: sk-... (48+ chars)
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[APIKEY-REDACTED]"),
    # Phone numbers: (123) 456-7890, 123-456-7890, 1234567890
    (re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE-REDACTED]"),
    # Credit card: 16 digits with optional separators
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CC-REDACTED]"),
]

# Log levels where PII should be redacted (INFO and above)
_REDACT_LEVELS = {"INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}


def sanitize_pii(message: str) -> str:
    """Redact PII patterns from a log message."""
    for pattern, replacement in _PII_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


def _pii_filter(record: dict) -> bool:
    """Loguru filter that redacts PII in INFO+ level messages.

    DEBUG messages are left untouched for development use.
    """
    if record["level"].name in _REDACT_LEVELS:
        record["message"] = sanitize_pii(record["message"])
    return True


def setup_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        filter=_pii_filter,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
    )
    logger.add(
        "reports/ui_agent.log",
        level="DEBUG",
        filter=_pii_filter,
        rotation="10 MB",
        retention="7 days",
    )
