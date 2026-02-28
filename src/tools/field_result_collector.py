from __future__ import annotations

from threading import Lock


class FieldResultCollector:
    """Thread-safe collector for field action results during crew execution."""

    def __init__(self) -> None:
        self._results: list[dict[str, str]] = []
        self._lock = Lock()

    def record(
        self,
        field_id: str,
        selector: str,
        value: str,
        status: str,
        error_message: str = "",
    ) -> None:
        with self._lock:
            self._results.append(
                {
                    "field_id": field_id,
                    "selector": selector,
                    "value": value,
                    "status": status,
                    "error_message": error_message,
                }
            )

    def get_results(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._results)

    def clear(self) -> None:
        with self._lock:
            self._results.clear()
