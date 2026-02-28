from __future__ import annotations

from pydantic import BaseModel

from .page_result import PageResult


class TestReport(BaseModel):
    test_case_id: str
    url: str
    overall_status: str  # PASS / PASS_WITH_RETRIES / PARTIAL / FAIL / ERROR
    total_pages: int
    pages_completed: int
    pages: list[PageResult]
    screenshots: list[str]
    start_time: str
    end_time: str
    duration_seconds: float
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_message: str = ""
