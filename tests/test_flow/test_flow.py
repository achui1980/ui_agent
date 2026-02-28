"""Tests for the FormTestFlow state management and multi-page loop."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

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

    def test_nested_json(self):
        text = 'prefix {"passed": true, "data": {"key": "val"}} suffix'
        result = FormTestFlow._extract_json(text)
        assert result["passed"] is True
        assert result["data"]["key"] == "val"

    def test_multiple_json_takes_last(self):
        text = '{"first": 1} some text {"second": 2}'
        result = FormTestFlow._extract_json(text)
        assert "second" in result


# ---------------------------------------------------------------------------
# Helpers for multi-page tests
# ---------------------------------------------------------------------------


def _make_flow(settings=None, **state_kwargs) -> FormTestFlow:
    """Create a FormTestFlow with mock settings and pre-populated state."""
    if settings is None:
        mock_settings = MagicMock()
        mock_settings.awa_max_steps = 50
        mock_settings.awa_max_healing_attempts = 3
    else:
        mock_settings = settings
    flow = FormTestFlow(settings=mock_settings)
    # Manually set state fields
    for k, v in state_kwargs.items():
        setattr(flow.state, k, v)
    if not flow.state.start_time:
        flow.state.start_time = time.time()
    return flow


def _crew_result_json(
    passed: bool = True,
    new_page_id: str = "page_0",
    is_final_page: bool = False,
    consumed_keys: list[str] | None = None,
    validation_errors: list | None = None,
    screenshot_path: str = "",
) -> str:
    """Build a JSON string mimicking crew verification output."""
    return json.dumps(
        {
            "passed": passed,
            "new_page_id": new_page_id,
            "is_final_page": is_final_page,
            "consumed_keys": consumed_keys or [],
            "validation_errors": validation_errors or [],
            "screenshot_path": screenshot_path,
        }
    )


# ---------------------------------------------------------------------------
# _update_state_from_crew_result tests
# ---------------------------------------------------------------------------


class TestUpdateStateFromCrewResult:
    def test_successful_page(self):
        flow = _make_flow()
        result = _crew_result_json(
            passed=True,
            new_page_id="step_2",
            consumed_keys=["first_name", "last_name"],
            screenshot_path="/tmp/screenshot.png",
        )
        flow._update_state_from_crew_result(result)

        assert flow.state.verification_passed is True
        assert flow.state.current_page_id == "step_2"
        assert flow.state.consumed_fields == ["first_name", "last_name"]
        assert "/tmp/screenshot.png" in flow.state.screenshots
        assert len(flow.state.page_results) == 1
        assert flow.state.page_results[0]["verification_passed"] is True

    def test_failed_page_with_errors(self):
        flow = _make_flow()
        result = _crew_result_json(
            passed=False,
            validation_errors=[
                {"field": "email", "message": "Invalid email format"},
                "Phone is required",
            ],
        )
        flow._update_state_from_crew_result(result)

        assert flow.state.verification_passed is False
        assert "Invalid email format" in flow.state.validation_errors
        assert "Phone is required" in flow.state.validation_errors

    def test_final_page_sets_completion(self):
        flow = _make_flow()
        result = _crew_result_json(passed=True, is_final_page=True)
        flow._update_state_from_crew_result(result)

        assert flow.state.current_page_id == "completion"

    def test_consumed_fields_accumulate(self):
        flow = _make_flow(consumed_fields=["first_name"])
        result = _crew_result_json(consumed_keys=["last_name", "email"])
        flow._update_state_from_crew_result(result)

        assert flow.state.consumed_fields == ["first_name", "last_name", "email"]

    def test_unparseable_result_with_error_keyword(self):
        flow = _make_flow()
        flow._update_state_from_crew_result("Something went wrong, error occurred")

        assert flow.state.verification_passed is False
        assert len(flow.state.validation_errors) == 1

    def test_unparseable_result_without_error_keyword(self):
        flow = _make_flow()
        flow._update_state_from_crew_result("All looks good, no issues")

        assert flow.state.verification_passed is True

    def test_page_results_record_retry_count(self):
        flow = _make_flow(retry_count=2)
        result = _crew_result_json(passed=False)
        flow._update_state_from_crew_result(result)

        assert flow.state.page_results[0]["retry_count"] == 2

    def test_field_results_parsed(self):
        flow = _make_flow()
        result = _crew_result_json(
            passed=True,
            is_final_page=True,
            consumed_keys=["first_name", "email"],
        )
        data = json.loads(result)
        data["field_results"] = [
            {
                "field_id": "first_name",
                "selector": "#firstName",
                "value": "John",
                "status": "success",
            },
            {
                "field_id": "email",
                "selector": "#email",
                "value": "john@test.com",
                "status": "healed",
                "error_message": "Used JS fill",
            },
        ]
        flow._update_state_from_crew_result(json.dumps(data))
        assert len(flow.state.page_results) == 1
        assert "field_results" in flow.state.page_results[0]
        assert len(flow.state.page_results[0]["field_results"]) == 2


# ---------------------------------------------------------------------------
# _run_page_loop tests (multi-page scenarios)
# ---------------------------------------------------------------------------


class TestRunPageLoop:
    """Test the unified page loop that drives multi-page form processing."""

    def _setup_flow_with_mock_process(
        self, page_sequence: list[dict], **state_kwargs
    ) -> FormTestFlow:
        """Create a flow whose process_page cycles through page_sequence.

        Each entry in page_sequence is a dict passed to _crew_result_json,
        representing one crew result. The mock also sets up a browser manager
        and report generation stub.
        """
        flow = _make_flow(
            test_case_id="TC_MULTI",
            target_url="http://example.com/form",
            test_case_data={"f1": "v1", "f2": "v2", "f3": "v3"},
            **state_kwargs,
        )

        # Build the sequence of crew results
        call_count = {"n": 0}

        def mock_process_page():
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(page_sequence):
                crew_result = _crew_result_json(**page_sequence[idx])
                flow._update_state_from_crew_result(crew_result)
            else:
                # Safety: should not be called beyond sequence
                flow.state.verification_passed = True
                flow.state.current_page_id = "completion"
            return "crew_done"

        flow.process_page = mock_process_page

        # Mock generate_report to avoid browser/report file dependencies
        flow.generate_report = lambda: {
            "overall_status": flow.state.overall_status or "PASS",
            "pages": flow.state.page_results,
            "total_pages": len(flow.state.page_results),
        }

        return flow

    def test_single_page_completion(self):
        """Single page form: pass on first try, is_final_page=True."""
        flow = self._setup_flow_with_mock_process(
            [
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["f1", "f2", "f3"],
                },
            ]
        )

        report = flow._run_page_loop()

        # page_index increments after each process_page, so 0 -> 1
        assert flow.state.current_page_index == 1
        assert flow.state.current_page_id == "completion"
        assert len(flow.state.page_results) == 1
        assert flow.state.consumed_fields == ["f1", "f2", "f3"]

    def test_three_page_form(self):
        """Three-page form: each page passes and advances, last is final."""
        flow = self._setup_flow_with_mock_process(
            [
                {
                    "passed": True,
                    "new_page_id": "step_1",
                    "consumed_keys": ["f1"],
                },
                {
                    "passed": True,
                    "new_page_id": "step_2",
                    "consumed_keys": ["f2"],
                },
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["f3"],
                },
            ]
        )

        report = flow._run_page_loop()

        # page_index increments after each process_page: 0->1->2->3
        assert flow.state.current_page_index == 3
        assert flow.state.current_page_id == "completion"
        assert len(flow.state.page_results) == 3
        assert flow.state.consumed_fields == ["f1", "f2", "f3"]

    def test_retry_then_pass(self):
        """Page fails verification, retries, then passes."""
        flow = self._setup_flow_with_mock_process(
            [
                {
                    "passed": False,
                    "validation_errors": [{"message": "Email invalid"}],
                },
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["f1"],
                },
            ]
        )

        report = flow._run_page_loop()

        assert flow.state.retry_count == 1
        assert flow.state.current_page_id == "completion"
        assert len(flow.state.page_results) == 2
        # page_index increments after each call: 0->1->2
        assert flow.state.current_page_index == 2

    def test_max_retries_exceeded(self):
        """Page fails all retries, loop exits with errors."""
        flow = self._setup_flow_with_mock_process(
            [
                {"passed": False, "validation_errors": ["Error 1"]},
                {"passed": False, "validation_errors": ["Error 2"]},
                {"passed": False, "validation_errors": ["Error 3"]},
                {"passed": False, "validation_errors": ["Error 4"]},
            ]
        )

        report = flow._run_page_loop()

        # max_retries=3, so: initial + 3 retries = 4 calls total
        assert flow.state.retry_count == 3
        assert flow.state.verification_passed is False
        assert len(flow.state.page_results) == 4
        # page_index increments after each call: 0->1->2->3->4
        assert flow.state.current_page_index == 4

    def test_multi_page_with_retry_on_second_page(self):
        """Page 1 passes, page 2 fails once then passes, page 3 is final."""
        flow = self._setup_flow_with_mock_process(
            [
                # Page 1: passes immediately
                {
                    "passed": True,
                    "new_page_id": "personal_info",
                    "consumed_keys": ["f1"],
                },
                # Page 2: first attempt fails
                {
                    "passed": False,
                    "validation_errors": [{"message": "State is required"}],
                },
                # Page 2: retry succeeds
                {
                    "passed": True,
                    "new_page_id": "address_info",
                    "consumed_keys": ["f2"],
                },
                # Page 3: final page
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["f3"],
                },
            ]
        )

        report = flow._run_page_loop()

        # page_index increments after each call: 0->1->2->3->4
        assert flow.state.current_page_index == 4
        assert flow.state.current_page_id == "completion"
        assert flow.state.consumed_fields == ["f1", "f2", "f3"]
        # 4 total process_page calls: page1 + page2_fail + page2_retry + page3
        assert len(flow.state.page_results) == 4

    def test_retry_count_resets_on_new_page(self):
        """Retry count should reset to 0 when advancing to a new page."""
        flow = self._setup_flow_with_mock_process(
            [
                # Page 1: fail once, then pass
                {"passed": False, "validation_errors": ["err"]},
                {
                    "passed": True,
                    "new_page_id": "page_2",
                    "consumed_keys": ["f1"],
                },
                # Page 2: should start with retry_count=0
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["f2"],
                },
            ]
        )

        report = flow._run_page_loop()

        # After advancing to page 2, retry_count should have been reset
        assert flow.state.retry_count == 0
        # page_index increments after each call: 0->1->2->3
        assert flow.state.current_page_index == 3

    def test_max_pages_safety_limit(self):
        """Loop should exit when max_pages is reached."""
        # Create a flow that always passes but never is_final_page
        never_ending = [{"passed": True, "new_page_id": f"page_{i}"} for i in range(10)]
        flow = self._setup_flow_with_mock_process(
            never_ending,
            max_pages=3,
        )

        # Override process_page to respect max_pages
        original_process = flow.process_page
        call_count = {"n": 0}

        def process_with_limit():
            if flow.state.current_page_index >= flow.state.max_pages:
                flow.state.overall_status = "PARTIAL"
                flow.state.verification_passed = True
                flow.state.current_page_id = "completion"
                return "max_pages_reached"
            call_count["n"] += 1
            return original_process()

        flow.process_page = process_with_limit

        report = flow._run_page_loop()

        # Should have processed exactly max_pages pages before hitting limit.
        # page_index increments after each process_page call:
        # 3 real pages + 1 call that hits the limit = 4 increments
        assert flow.state.current_page_index == 4
        assert flow.state.overall_status == "PARTIAL"

    def test_consumed_fields_accumulate_across_pages(self):
        """Consumed fields from all pages should accumulate in state."""
        flow = self._setup_flow_with_mock_process(
            [
                {
                    "passed": True,
                    "new_page_id": "p1",
                    "consumed_keys": ["first_name", "last_name"],
                },
                {
                    "passed": True,
                    "new_page_id": "p2",
                    "consumed_keys": ["address", "city"],
                },
                {
                    "passed": True,
                    "is_final_page": True,
                    "consumed_keys": ["card_number"],
                },
            ]
        )

        flow._run_page_loop()

        assert flow.state.consumed_fields == [
            "first_name",
            "last_name",
            "address",
            "city",
            "card_number",
        ]

    def test_validation_errors_cleared_on_advance(self):
        """Validation errors from previous page should be cleared when advancing."""
        flow = self._setup_flow_with_mock_process(
            [
                # Page 1: fail with errors, then pass
                {"passed": False, "validation_errors": ["bad email"]},
                {"passed": True, "new_page_id": "p2", "consumed_keys": ["f1"]},
                # Page 2: should start clean
                {"passed": True, "is_final_page": True, "consumed_keys": ["f2"]},
            ]
        )

        flow._run_page_loop()

        # After advancing past page 1 (which had errors), validation_errors
        # should be empty for page 2
        assert flow.state.validation_errors == []

    def test_screenshots_accumulate(self):
        """Screenshots from all pages should accumulate."""
        flow = self._setup_flow_with_mock_process(
            [
                {
                    "passed": True,
                    "new_page_id": "p1",
                    "screenshot_path": "/tmp/page1.png",
                },
                {
                    "passed": True,
                    "is_final_page": True,
                    "screenshot_path": "/tmp/page2.png",
                },
            ]
        )

        flow._run_page_loop()

        assert flow.state.screenshots == ["/tmp/page1.png", "/tmp/page2.png"]


# ---------------------------------------------------------------------------
# generate_report tests
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_all_pages_pass_reaching_completion(self):
        """All pages pass on first try and reach completion -> PASS."""
        flow = _make_flow(
            test_case_id="TC_REPORT",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=2,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PASS"
        assert result["pages_completed"] == 2
        assert result["total_pages"] == 2

    def test_pass_with_retries(self):
        """Reach completion but with retries -> PASS_WITH_RETRIES."""
        flow = _make_flow(
            test_case_id="TC_RETRIES",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": False,
                    "validation_errors": ["err"],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 1,
                },
                {
                    "page_index": 2,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=3,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PASS_WITH_RETRIES"

    def test_partial_pass(self):
        """Some pages pass but didn't reach completion -> PARTIAL."""
        flow = _make_flow(
            test_case_id="TC_PARTIAL",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "p2",
                    "verification_passed": False,
                    "validation_errors": ["some error"],
                    "retry_count": 3,
                },
            ],
            current_page_index=2,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PARTIAL"
        assert result["pages_completed"] == 1

    def test_all_fail(self):
        flow = _make_flow(
            test_case_id="TC_FAIL",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": False,
                    "validation_errors": ["err1"],
                    "retry_count": 3,
                },
            ],
            current_page_index=1,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "FAIL"
        assert result["pages_completed"] == 0

    def test_fields_filled_populated(self):
        flow = _make_flow(
            test_case_id="TC_FIELDS",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                    "field_results": [
                        {
                            "field_id": "name",
                            "selector": "#name",
                            "value": "John",
                            "status": "success",
                            "error_message": "",
                        },
                    ],
                },
            ],
            current_page_index=1,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert len(result["pages"]) == 1
        page = result["pages"][0]
        assert len(page["fields_filled"]) == 1
        assert page["fields_filled"][0]["field_id"] == "name"

    def test_no_page_results(self):
        flow = _make_flow(
            test_case_id="TC_EMPTY",
            target_url="http://example.com",
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "FAIL"


# ---------------------------------------------------------------------------
# Multiple test case execution
# ---------------------------------------------------------------------------


class TestConfigConnection:
    """Test that config fields are connected to runtime behavior."""

    def test_max_pages_from_settings(self):
        settings = MagicMock()
        settings.awa_max_steps = 10
        settings.awa_max_healing_attempts = 5
        flow = FormTestFlow(settings=settings)
        assert flow.state.max_pages == 10
        assert flow.state.max_retries == 5

    def test_default_settings_values(self):
        """Flow should use real Settings defaults when no mock is provided."""
        with patch("src.flow.form_test_flow.get_settings") as mock_get:
            mock_settings = MagicMock()
            mock_settings.awa_max_steps = 50
            mock_settings.awa_max_healing_attempts = 3
            mock_get.return_value = mock_settings
            flow = FormTestFlow()
            assert flow.state.max_pages == 50
            assert flow.state.max_retries == 3

    def test_cli_overrides_config(self):
        """CLI args should override config when set after __init__."""
        settings = MagicMock()
        settings.awa_max_steps = 10
        settings.awa_max_healing_attempts = 5
        flow = FormTestFlow(settings=settings)
        # Simulate CLI override (as main.py does)
        flow.state.max_pages = 99
        flow.state.max_retries = 7
        assert flow.state.max_pages == 99
        assert flow.state.max_retries == 7


class TestMultipleTestCases:
    def test_parse_loads_all_cases(self, tmp_path):
        """Parser should return all test cases from a multi-case file."""
        import json

        data = [
            {"test_id": "TC1", "data": {"name": "Alice"}},
            {"test_id": "TC2", "data": {"name": "Bob"}},
        ]
        path = tmp_path / "multi.json"
        path.write_text(json.dumps(data))

        from src.parsers.parser_factory import parse_test_file

        cases = parse_test_file(str(path), "http://example.com")
        assert len(cases) == 2
        assert cases[0].test_id == "TC1"
        assert cases[1].test_id == "TC2"


# ---------------------------------------------------------------------------
# FR-02: Error recovery tests
# ---------------------------------------------------------------------------


class TestErrorRecovery:
    """Test that fatal errors during page processing produce ERROR reports."""

    def test_process_page_exception_produces_error_report(self):
        """When process_page raises, _run_page_loop catches it and generates a report."""
        flow = _make_flow(
            test_case_id="TC_ERROR",
            target_url="http://example.com",
            test_case_data={"f1": "v1"},
        )

        def exploding_process_page():
            raise RuntimeError("Browser crashed unexpectedly")

        flow.process_page = exploding_process_page

        # Mock generate_report to avoid file/browser dependencies
        captured = {}

        def mock_generate_report():
            captured["status"] = flow.state.overall_status
            captured["error_message"] = flow.state.error_message
            captured["page_results"] = list(flow.state.page_results)
            return {
                "overall_status": flow.state.overall_status,
                "error_message": flow.state.error_message,
                "pages": flow.state.page_results,
            }

        flow.generate_report = mock_generate_report

        report = flow._run_page_loop()

        assert report["overall_status"] == "ERROR"
        assert "Browser crashed unexpectedly" in report["error_message"]

    def test_error_preserves_partial_results(self):
        """If some pages succeed before an error, partial results are kept."""
        flow = _make_flow(
            test_case_id="TC_PARTIAL_ERROR",
            target_url="http://example.com",
            test_case_data={"f1": "v1", "f2": "v2"},
        )

        call_count = {"n": 0}

        def process_then_explode():
            idx = call_count["n"]
            call_count["n"] += 1
            if idx == 0:
                # First call succeeds
                crew_result = _crew_result_json(
                    passed=True,
                    new_page_id="step_1",
                    consumed_keys=["f1"],
                )
                flow._update_state_from_crew_result(crew_result)
                return "crew_done"
            else:
                raise RuntimeError("Network timeout")

        flow.process_page = process_then_explode

        def mock_generate_report():
            return {
                "overall_status": flow.state.overall_status,
                "error_message": flow.state.error_message,
                "pages": list(flow.state.page_results),
            }

        flow.generate_report = mock_generate_report

        report = flow._run_page_loop()

        assert report["overall_status"] == "ERROR"
        assert "Network timeout" in report["error_message"]
        # The first page result should still be present
        assert len(report["pages"]) == 1
        assert report["pages"][0]["verification_passed"] is True

    def test_error_status_preserved_in_generate_report(self):
        """generate_report should not overwrite ERROR status."""
        flow = _make_flow(
            test_case_id="TC_ERROR_REPORT",
            target_url="http://example.com",
            overall_status="ERROR",
            error_message="Something broke",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=1,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "ERROR"
        assert result["error_message"] == "Something broke"


# ---------------------------------------------------------------------------
# FR-03: Four-level status tests
# ---------------------------------------------------------------------------


class TestFourLevelStatus:
    """Test the PASS / PASS_WITH_RETRIES / PARTIAL / FAIL status logic."""

    def test_pass_all_first_try_with_completion(self):
        """All pages pass on first try and reach completion -> PASS."""
        flow = _make_flow(
            test_case_id="TC_PASS",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=2,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PASS"

    def test_pass_with_retries(self):
        """Reach completion but some pages had retries -> PASS_WITH_RETRIES."""
        flow = _make_flow(
            test_case_id="TC_PWR",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": False,
                    "validation_errors": ["err"],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 1,
                },
                {
                    "page_index": 2,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=3,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PASS_WITH_RETRIES"

    def test_partial_no_completion(self):
        """Some pages passed but didn't reach completion -> PARTIAL."""
        flow = _make_flow(
            test_case_id="TC_PARTIAL",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "p2",
                    "verification_passed": False,
                    "validation_errors": ["failed"],
                    "retry_count": 3,
                },
            ],
            current_page_index=2,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "PARTIAL"

    def test_fail_no_pages_passed(self):
        """No pages passed -> FAIL."""
        flow = _make_flow(
            test_case_id="TC_FAIL",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": False,
                    "validation_errors": ["err"],
                    "retry_count": 3,
                },
            ],
            current_page_index=1,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "FAIL"

    def test_fail_no_results(self):
        """No page results at all -> FAIL."""
        flow = _make_flow(
            test_case_id="TC_EMPTY",
            target_url="http://example.com",
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["overall_status"] == "FAIL"


# ---------------------------------------------------------------------------
# FR-04: screenshot_path population tests
# ---------------------------------------------------------------------------


class TestScreenshotPath:
    """Test that screenshot_path is populated in page_results."""

    def test_screenshot_path_from_crew_result(self):
        """screenshot_path from crew result should appear in page_result."""
        flow = _make_flow()
        result = _crew_result_json(
            passed=True,
            is_final_page=True,
            screenshot_path="/tmp/page_shot.png",
        )
        flow._update_state_from_crew_result(result)

        assert flow.state.page_results[0]["screenshot_path"] == "/tmp/page_shot.png"

    def test_screenshot_path_falls_back_to_latest(self):
        """When crew result has no screenshot, use latest from state.screenshots."""
        flow = _make_flow(screenshots=["/tmp/earlier.png"])
        result = _crew_result_json(
            passed=True,
            is_final_page=True,
            screenshot_path="",
        )
        flow._update_state_from_crew_result(result)

        assert flow.state.page_results[0]["screenshot_path"] == "/tmp/earlier.png"

    def test_screenshot_path_empty_when_none_available(self):
        """When no screenshots at all, screenshot_path should be empty."""
        flow = _make_flow()
        result = _crew_result_json(
            passed=True,
            is_final_page=True,
            screenshot_path="",
        )
        flow._update_state_from_crew_result(result)

        assert flow.state.page_results[0]["screenshot_path"] == ""

    def test_screenshot_path_in_generated_report(self):
        """screenshot_path should propagate through to the generated report."""
        flow = _make_flow(
            test_case_id="TC_SS",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                    "screenshot_path": "/tmp/final.png",
                },
            ],
            current_page_index=1,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert result["pages"][0]["screenshot_path"] == "/tmp/final.png"


# ---------------------------------------------------------------------------
# FR-05: page_index increment tests
# ---------------------------------------------------------------------------


class TestPageIndexIncrement:
    """Test that page_index increments after every process_page call."""

    def test_page_index_sequential_across_retries(self):
        """Each page_result should have a unique sequential page_index."""
        flow = _make_flow(
            test_case_id="TC_IDX",
            target_url="http://example.com",
            test_case_data={"f1": "v1"},
        )

        call_count = {"n": 0}

        def mock_process_page():
            idx = call_count["n"]
            call_count["n"] += 1
            pages = [
                {"passed": False, "validation_errors": ["err"]},
                {"passed": True, "is_final_page": True, "consumed_keys": ["f1"]},
            ]
            if idx < len(pages):
                crew_result = _crew_result_json(**pages[idx])
                flow._update_state_from_crew_result(crew_result)
            return "crew_done"

        flow.process_page = mock_process_page
        flow.generate_report = lambda: {
            "pages": flow.state.page_results,
        }

        report = flow._run_page_loop()

        # First call uses index 0, second call uses index 1
        assert report["pages"][0]["page_index"] == 0
        assert report["pages"][1]["page_index"] == 1
        # After two calls, current_page_index should be 2
        assert flow.state.current_page_index == 2

    def test_total_pages_matches_page_results_count(self):
        """total_pages in report should equal len(page_results)."""
        flow = _make_flow(
            test_case_id="TC_TOTAL",
            target_url="http://example.com",
            page_results=[
                {
                    "page_index": 0,
                    "page_id": "p1",
                    "verification_passed": False,
                    "validation_errors": ["err"],
                    "retry_count": 0,
                },
                {
                    "page_index": 1,
                    "page_id": "p1",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 1,
                },
                {
                    "page_index": 2,
                    "page_id": "completion",
                    "verification_passed": True,
                    "validation_errors": [],
                    "retry_count": 0,
                },
            ],
            current_page_index=3,
        )

        with (
            patch(
                "src.flow.form_test_flow.save_json_report", return_value="/tmp/r.json"
            ),
            patch(
                "src.flow.form_test_flow.save_html_report", return_value="/tmp/r.html"
            ),
        ):
            result = flow.generate_report()

        assert (
            result["total_pages"] == 3
        )  # len(page_results), not current_page_index + 1
