from pydantic import BaseModel


class FieldActionResult(BaseModel):
    field_id: str
    selector: str
    value: str
    status: str  # success / failed / healed
    error_message: str = ""


class PageResult(BaseModel):
    page_index: int
    page_id: str
    fields_filled: list[FieldActionResult]
    verification_passed: bool
    validation_errors: list[str] = []
    retry_count: int = 0
    screenshot_path: str = ""
    duration_seconds: float = 0.0
    task_durations: dict[str, float] = {}  # e.g. {"analyze": 5.2, "map": 1.1, ...}
    token_usage: dict[str, int] = {}  # e.g. {"total_tokens": 1200, ...}
