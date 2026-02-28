"""Tests for report generation (JSON and HTML)."""

from __future__ import annotations

import json
import os

import pytest

from src.reporting.json_report import save_json_report
from src.reporting.html_report import save_html_report


class TestJsonReport:
    def test_save_json_report(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report = {"test_case_id": "TC1", "overall_status": "PASS", "pages": []}
        path = save_json_report(report, "TC1")
        assert os.path.exists(path)
        with open(path) as f:
            saved = json.load(f)
        assert saved["overall_status"] == "PASS"


class TestHtmlReport:
    def test_save_html_report(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report = {
            "test_case_id": "TC1",
            "overall_status": "PASS",
            "url": "http://example.com",
            "total_pages": 1,
            "pages_completed": 1,
            "pages": [],
            "screenshots": [],
            "start_time": "2026-01-01 00:00:00",
            "end_time": "2026-01-01 00:01:00",
            "duration_seconds": 60.0,
            "total_tokens": 100,
            "prompt_tokens": 80,
            "completion_tokens": 20,
        }
        path = save_html_report(report, "TC1")
        assert os.path.exists(path)
        with open(path) as f:
            html = f.read()
        assert "PASS" in html
