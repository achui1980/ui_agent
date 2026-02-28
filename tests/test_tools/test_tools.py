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
    def test_select_native_by_label(self, mock_page):
        mock_page.eval_on_selector.return_value = "select"
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state", label="Illinois")
        assert "SUCCESS" in result
        mock_page.select_option.assert_called_once_with("#state", label="Illinois")

    def test_select_native_by_value(self, mock_page):
        mock_page.eval_on_selector.return_value = "select"
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state", value="IL")
        assert "SUCCESS" in result
        mock_page.select_option.assert_called_once_with("#state", value="IL")

    def test_select_no_label_or_value(self, mock_page):
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state")
        assert "FAILED" in result

    def test_select_react_fallback(self, mock_page):
        """When eval_on_selector fails (not a native select), try react-select path."""
        mock_page.eval_on_selector.side_effect = Exception("not a select")
        tool = SelectOptionTool(page=mock_page)
        result = tool._run(selector="#state", label="Illinois")
        # Should attempt react-select or generic path, not crash
        assert isinstance(result, str)


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
        result = tool._run(selector="#upload", file_path="/nonexistent/file.pdf")
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

    def test_default_screenshot_dir(self, mock_page):
        tool = ScreenshotTool(page=mock_page)
        assert tool.screenshot_dir == "reports/screenshots"

    def test_custom_screenshot_dir(self, mock_page, tmp_path):
        custom_dir = str(tmp_path / "custom_shots")
        tool = ScreenshotTool(page=mock_page, screenshot_dir=custom_dir)
        result = tool._run()
        assert "SUCCESS" in result
        mock_page.screenshot.assert_called_once()
        call_args = mock_page.screenshot.call_args
        # The path should be within the custom directory
        called_path = call_args.kwargs.get("path", "")
        assert custom_dir in called_path


class TestScreenshotAnalysisToolConfig:
    def test_default_screenshot_dir(self, mock_page):
        from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

        tool = ScreenshotAnalysisTool(page=mock_page)
        assert tool.screenshot_dir == "reports/screenshots"

    def test_custom_screenshot_dir(self, mock_page, tmp_path):
        from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

        custom_dir = str(tmp_path / "custom_analysis")
        tool = ScreenshotAnalysisTool(
            page=mock_page,
            screenshot_dir=custom_dir,
            vlm_model="test-model",
            vlm_api_key="test-key",
        )
        # The tool should use the custom directory for screenshots
        # We can't run _run fully without VLM, but we can verify the field is set
        assert tool.screenshot_dir == custom_dir


class TestScreenshotAnalysisTool:
    def test_analysis_vlm_failure_heals(self, mock_page, tmp_path):
        """When VLM call fails, tool should return HEALED status."""
        from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

        tool = ScreenshotAnalysisTool(
            page=mock_page,
            vlm_model="test-model",
            vlm_api_key="test-key",
            screenshot_dir=str(tmp_path),
        )

        # Mock OpenAI — imported locally inside _run, so patch at the source
        with patch("openai.OpenAI") as MockClient:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API error")
            MockClient.return_value = mock_client

            result = tool._run("Describe the form")

        assert "HEALED" in result or "FAILED" in result


class TestFieldResultCollector:
    """Tests for the FieldResultCollector used in dual-layer field result collection."""

    def test_record_and_get(self):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        collector.record("name", "#name", "John", "success")
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["field_id"] == "name"
        assert results[0]["selector"] == "#name"
        assert results[0]["value"] == "John"
        assert results[0]["status"] == "success"
        assert results[0]["error_message"] == ""

    def test_record_with_error(self):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        collector.record("email", "#email", "bad", "failed", "FAILED: invalid")
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert results[0]["error_message"] == "FAILED: invalid"

    def test_multiple_records(self):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        collector.record("name", "#name", "John", "success")
        collector.record("email", "#email", "j@x.com", "success")
        collector.record("state", "#state", "IL", "healed")
        results = collector.get_results()
        assert len(results) == 3

    def test_clear(self):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        collector.record("name", "#name", "John", "success")
        collector.clear()
        assert len(collector.get_results()) == 0

    def test_get_returns_copy(self):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        collector.record("name", "#name", "John", "success")
        results1 = collector.get_results()
        results2 = collector.get_results()
        assert results1 == results2
        assert results1 is not results2


class TestToolCollectorIntegration:
    """Tests that tools correctly record results to a FieldResultCollector."""

    def test_fill_input_records_success(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        tool = FillInputTool(page=mock_page, collector=collector)
        result = tool._run(selector="#name", value="John")
        assert "SUCCESS" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["selector"] == "#name"
        assert results[0]["value"] == "John"

    def test_fill_input_records_healed(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        locator = mock_page.locator.return_value
        locator.fill.side_effect = Exception("fill failed")
        collector = FieldResultCollector()
        tool = FillInputTool(page=mock_page, collector=collector)
        result = tool._run(selector="#name", value="John")
        assert "HEALED" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "healed"

    def test_fill_input_records_failed(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        locator = mock_page.locator.return_value
        locator.fill.side_effect = Exception("fill failed")
        locator.click.side_effect = Exception("click also failed")
        collector = FieldResultCollector()
        tool = FillInputTool(page=mock_page, collector=collector)
        result = tool._run(selector="#name", value="John")
        assert "FAILED" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert results[0]["error_message"] != ""

    def test_fill_input_no_collector(self, mock_page):
        """Tool works fine without a collector (backward compatible)."""
        tool = FillInputTool(page=mock_page, collector=None)
        result = tool._run(selector="#name", value="John")
        assert "SUCCESS" in result

    def test_select_option_records_success(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        mock_page.eval_on_selector.return_value = "select"
        collector = FieldResultCollector()
        tool = SelectOptionTool(page=mock_page, collector=collector)
        result = tool._run(selector="#state", label="Illinois")
        assert "SUCCESS" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_checkbox_records_success(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        tool = CheckboxTool(page=mock_page, collector=collector)
        result = tool._run(selector="#agree", check=True)
        assert "SUCCESS" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["value"] == "True"

    def test_date_picker_records_success(self, mock_page):
        from src.tools.field_result_collector import FieldResultCollector

        collector = FieldResultCollector()
        tool = DatePickerTool(page=mock_page, collector=collector)
        result = tool._run(selector="#dob", value="01/15/1990")
        assert "SUCCESS" in result
        results = collector.get_results()
        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["value"] == "01/15/1990"
