"""Tests for test case parsers."""

from __future__ import annotations

import json
import os

import pytest

from src.parsers.csv_parser import parse_csv
from src.parsers.json_parser import parse_json
from src.parsers.yaml_parser import parse_yaml
from src.parsers.parser_factory import parse_test_file


class TestJsonParser:
    def test_parse_structured_json(self, tmp_path):
        data = [
            {
                "test_id": "TC1",
                "data": {"first_name": "John", "last_name": "Smith"},
            }
        ]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))

        result = parse_json(str(path), "http://example.com")
        assert len(result) == 1
        assert result[0].test_id == "TC1"
        assert result[0].data["first_name"] == "John"

    def test_parse_flat_json(self, tmp_path):
        data = {"first_name": "Jane", "email": "jane@test.com"}
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))

        result = parse_json(str(path), "http://example.com")
        assert len(result) == 1
        assert result[0].data["email"] == "jane@test.com"

    def test_parse_single_object(self, tmp_path):
        data = {
            "test_id": "TC2",
            "data": {"name": "Test"},
        }
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))

        result = parse_json(str(path), "http://example.com")
        assert len(result) == 1


class TestCsvParser:
    def test_parse_csv(self, tmp_path):
        csv_content = "test_id,first_name,last_name\nTC1,John,Smith\n"
        path = tmp_path / "test.csv"
        path.write_text(csv_content)

        result = parse_csv(str(path), "http://example.com")
        assert len(result) == 1
        assert result[0].data["first_name"] == "John"
        assert result[0].test_id == "TC1"


class TestYamlParser:
    def test_parse_yaml(self, tmp_path):
        yaml_content = """
- test_id: TC1
  data:
    first_name: John
    last_name: Smith
"""
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)

        result = parse_yaml(str(path), "http://example.com")
        assert len(result) == 1
        assert result[0].data["first_name"] == "John"


class TestParserFactory:
    def test_dispatch_json(self, tmp_path):
        data = [{"data": {"name": "Test"}}]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))

        result = parse_test_file(str(path), "http://example.com")
        assert len(result) == 1

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported"):
            parse_test_file("test.xyz", "http://example.com")
