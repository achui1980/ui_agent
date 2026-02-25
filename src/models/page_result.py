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
    validation_errors: list[dict] = []
    retry_count: int = 0
    screenshot_path: str = ""
