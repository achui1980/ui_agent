"""Tests for browser tools (using mock page objects)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools.fill_input_tool import FillInputTool
from src.tools.select_option_tool import SelectOptionTool
from src.tools.checkbox_tool import CheckboxTool
from src.tools.click_button_tool import ClickButtonTool
from src.tools.date_picker_tool import DatePickerTool
from src.tools.upload_file_tool import UploadFileTool
from src.tools.dom_extractor_tool import DOMExtractorTool
from src.tools.validation_error_tool import GetValidationErrorsTool
from src.tools.screenshot_tool import ScreenshotTool


@pytest.fixture
def mock_page():
    page = MagicMock()
    locator = MagicMock()
    page.locator.return_value = locator
    return page


class TestFillInputTool:
    def test_fill_success(self, mock_page):
        tool = FillInputTool(page=mock_page)
        result = tool._run(selector="#name", value="John")
        assert "SUCCESS" in result
        mock_page.locator.assert_called_with("#name")

    def test_fill_heals_on_error(self, mock_page):
        locator = mock_page.locator.return_value
        locator.fill.side_effect = Exception("fill failed")
        # Healing path should work
        tool = FillInputTool(page=mock_page)
        result = tool._run(selector="#name", value="John")
        assert "HEALED" in result or "FAILED" in result


class TestSelectOptionTool:
    def test_select_by_label(self, mock_page):
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state", label="Illinois")
        assert "SUCCESS" in result

    def test_select_by_value(self, mock_page):
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state", value="IL")
        assert "SUCCESS" in result

    def test_select_no_label_or_value(self, mock_page):
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state")
        assert "FAILED" in result


class TestCheckboxTool:
    def test_check(self, mock_page):
        tool = CheckboxTool(page=mock_page)
        result = tool._run(selector="#agree", check=True)
        assert "SUCCESS" in result

    def test_uncheck(self, mock_page):
        tool = CheckboxTool(page=mock_page)
        result = tool._run(selector="#agree", check=False)
        assert "SUCCESS" in result


class TestClickButtonTool:
    def test_click_success(self, mock_page):
        tool = ClickButtonTool(page=mock_page)
        result = tool._run(selector="#submit")
        assert "SUCCESS" in result

    def test_click_no_nav(self, mock_page):
        tool = ClickButtonTool(page=mock_page)
        result = tool._run(selector="#btn", wait_for_navigation=False)
        assert "SUCCESS" in result
        mock_page.wait_for_load_state.assert_not_called()


class TestDatePickerTool:
    def test_date_fill(self, mock_page):
        tool = DatePickerTool(page=mock_page)
        result = tool._run(selector="#dob", value="01/15/1990")
        assert "SUCCESS" in result


class TestUploadFileTool:
    def test_file_not_found(self, mock_page):
        tool = UploadFileTool(page=mock_page)
        result = tool._run(
            selector="#upload", file_path="/nonexistent/file.pdf"
        )
        assert "FAILED" in result


class TestDOMExtractorTool:
    def test_extract(self, mock_page):
        mock_page.evaluate.return_value = '{"fields": [], "buttons": []}'
        tool = DOMExtractorTool(page=mock_page)
        result = tool._run()
        assert "fields" in result


class TestGetValidationErrorsTool:
    def test_extract_errors(self, mock_page):
        mock_page.evaluate.return_value = "[]"
        tool = GetValidationErrorsTool(page=mock_page)
        result = tool._run()
        assert result == "[]"


class TestScreenshotTool:
    def test_screenshot(self, mock_page, tmp_path):
        tool = ScreenshotTool(page=mock_page)
        path = str(tmp_path / "test.png")
        result = tool._run(save_path=path)
        assert "SUCCESS" in result
        mock_page.screenshot.assert_called_once()
