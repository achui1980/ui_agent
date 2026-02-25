"""Tests for the FormTestFlow state management."""
from __future__ import annotations

import json

import pytest

from src.flow.form_test_flow import FormTestFlow, FormTestState


class TestFormTestState:
    def test_default_state(self):
        state = FormTestState()
        assert state.current_page_index == 0
        assert state.consumed_fields == []
        assert state.max_pages == 50
        assert state.max_retries == 3

    def test_state_serialization(self):
        state = FormTestState(
            test_case_id="TC1",
            target_url="http://example.com",
            test_case_data={"name": "John"},
        )
        d = state.model_dump()
        assert d["test_case_id"] == "TC1"


class TestExtractJson:
    def test_plain_json(self):
        result = FormTestFlow._extract_json('{"passed": true}')
        assert result["passed"] is True

    def test_json_in_text(self):
        text = 'Some text before {"passed": false, "errors": []} and after'
        result = FormTestFlow._extract_json(text)
        assert result["passed"] is False

    def test_no_json(self):
        with pytest.raises(ValueError):
            FormTestFlow._extract_json("no json here")
