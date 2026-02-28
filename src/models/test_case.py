from __future__ import annotations

from pydantic import BaseModel


class TestCase(BaseModel):
    test_id: str
    url: str
    data: dict[str, str]  # canonical_field_name -> value
    description: str = ""
    expected_outcome: str = "success"
