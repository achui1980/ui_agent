"""Tests for CLI commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from src.main import cli


class TestValidateCommand:
    def test_validate_json(self, tmp_path):
        data = [{"test_id": "TC1", "data": {"name": "Test"}}]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))

        runner = CliRunner()
        result = runner.invoke(
            cli, ["validate", str(path), "--url", "http://example.com"]
        )
        assert result.exit_code == 0
        assert "TC1" in result.output

    def test_validate_unsupported(self):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["validate", "test.xyz", "--url", "http://example.com"]
        )
        assert result.exit_code != 0

    def test_validate_txt_without_url(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("some text")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(path)])
        assert result.exit_code != 0


class TestGenerateCommand:
    def test_generate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Auto-fill" in result.output
        assert "dynamically generated" in result.output

    def test_generate_requires_url(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0

    def test_generate_accepts_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert "--max-pages" in result.output
        assert "--max-retries" in result.output
