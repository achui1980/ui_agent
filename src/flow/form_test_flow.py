from __future__ import annotations

import json
import os
import time
from typing import Any

from crewai.flow.flow import (
    Flow,
    listen,
    router,
    start,
)  # router used by route_after_parse
from loguru import logger
from pydantic import BaseModel

from src.browser.browser_manager import BrowserManager
from src.config import Settings, get_settings
from src.flow.page_crew import build_page_crew
from src.models import TestCase, TestReport, PageResult, FieldActionResult
from src.parsers.parser_factory import parse_test_file
from src.reporting.json_report import save_json_report
from src.reporting.html_report import save_html_report


class FormTestState(BaseModel):
    """Flow global state."""

    # Input
    test_input_path: str = ""
    target_url: str = ""

    # Parsed test case
    test_case_data: dict[str, str] = {}
    test_case_id: str = ""
    description: str = ""
    expected_outcome: str = "success"

    # Page context (for NL parsing)
    page_context: dict = {}

    # Page loop state
    current_page_index: int = 0
    consumed_fields: list[str] = []
    page_results: list[dict] = []
    max_pages: int = 50

    # Current page state
    current_page_id: str = ""
    verification_passed: bool = False
    retry_count: int = 0
    max_retries: int = 3
    validation_errors: list[str] = []

    # Final result
    overall_status: str = ""  # PASS / FAIL / PARTIAL
    screenshots: list[str] = []
    start_time: float = 0.0


class FormTestFlow(Flow[FormTestState]):
    def __init__(self, settings: Settings | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._settings = settings or get_settings()
        self._browser_manager: BrowserManager | None = None
        # Connect config to state defaults
        self.state.max_pages = self._settings.awa_max_steps
        self.state.max_retries = self._settings.awa_max_healing_attempts

    @start()
    def parse_test_case(self) -> str:
        """Detect input type. NL files need page analysis first."""
        self.state.start_time = time.time()

        # If test case data was pre-loaded (multi-case execution), skip parsing
        if self.state.test_case_id:
            logger.info(
                f"Test case '{self.state.test_case_id}' pre-loaded, skipping parse"
            )
            return "parsed"

        ext = os.path.splitext(self.state.test_input_path)[1].lower()

        if ext == ".txt":
            logger.info("Natural language input detected, need page analysis first")
            return "needs_page_analysis"

        logger.info(f"Parsing test case from: {self.state.test_input_path}")

        test_cases = parse_test_file(
            self.state.test_input_path,
            self.state.target_url,
            self._settings,
        )
        if not test_cases:
            raise ValueError("No test cases found in input file")

        tc = test_cases[0]
        self._load_test_case(tc)

        logger.info(f"Test case '{tc.test_id}' loaded with {len(tc.data)} data fields")
        return "parsed"

    @router(parse_test_case)
    def route_after_parse(self) -> str:
        """Route based on whether NL pre-analysis is needed."""
        if self.state.test_case_id:
            # Already parsed (non-NL input)
            return "open_browser"
        else:
            # NL input — needs page analysis first
            return "pre_analyze"

    @listen("pre_analyze")
    def pre_analyze_page(self) -> dict:
        """For NL input: open browser, extract DOM, then parse NL with page context."""
        if not self.state.target_url:
            raise ValueError("URL is required for natural language (.txt) test files")

        logger.info("Pre-analyzing page for NL context...")

        # Start browser and navigate
        self._browser_manager = BrowserManager(self._settings)
        self._browser_manager.start()
        self._browser_manager.navigate(self.state.target_url)

        # Extract DOM field info
        from src.tools.dom_extractor_tool import DOMExtractorTool

        extractor = DOMExtractorTool(page=self._browser_manager.page)
        result = extractor._run()
        page_context = json.loads(result)
        self.state.page_context = page_context

        logger.info(
            f"Page context extracted: {len(page_context.get('fields', []))} fields"
        )

        # Parse NL with context
        test_cases = parse_test_file(
            self.state.test_input_path,
            self.state.target_url,
            self._settings,
            page_context=page_context,
        )
        if not test_cases:
            raise ValueError("No test cases found in NL input")

        tc = test_cases[0]
        self._load_test_case(tc)

        logger.info(
            f"NL test case '{tc.test_id}' parsed with "
            f"{len(tc.data)} fields (context-aware)"
        )

        # Drive the page processing loop (browser already started above).
        return self._run_page_loop()

    def _run_page_loop(self) -> dict:
        """Drive the page-processing loop.

        This is the unified page loop engine used by both NL and non-NL paths.
        It calls process_page() directly and handles routing decisions
        (next page / retry / complete) in an explicit while-loop, avoiding
        the CrewAI Flow event system which does not support re-entrant
        method calls from @listen handlers.
        """
        while True:
            result = self.process_page()  # noqa: arg-type

            # Decide next step (mirrors decide_next_step logic)
            if self.state.verification_passed:
                if self.state.current_page_id == "completion":
                    logger.info("Form completed successfully")
                    break
                logger.info("Page passed, advancing to next page")
                self.state.current_page_index += 1
                self.state.retry_count = 0
                self.state.validation_errors = []
                continue
            elif self.state.retry_count < self.state.max_retries:
                logger.info(
                    f"Verification failed, retrying "
                    f"({self.state.retry_count + 1}/{self.state.max_retries})"
                )
                self.state.retry_count += 1
                continue
            else:
                logger.warning("Max retries exceeded, completing with errors")
                break

        return self.generate_report()

    def _load_test_case(self, tc: TestCase) -> None:
        """Load a parsed TestCase into flow state."""
        self.state.test_case_data = tc.data
        self.state.test_case_id = tc.test_id
        self.state.target_url = tc.url or self.state.target_url
        self.state.description = tc.description
        self.state.expected_outcome = tc.expected_outcome

    @listen("open_browser")
    def open_browser_and_navigate(self) -> dict:
        """Start Playwright, navigate to target URL, and drive the page loop."""
        if not self.state.target_url:
            raise ValueError("No target URL specified")

        # If browser already started (from NL pre-analysis), skip
        if self._browser_manager is not None:
            logger.info("Browser already started (from NL pre-analysis), skipping")
        else:
            self._browser_manager = BrowserManager(self._settings)
            self._browser_manager.start()
            self._browser_manager.navigate(self.state.target_url)

        logger.info("Browser ready, starting page processing")
        return self._run_page_loop()

    def process_page(self) -> str:
        """Trigger PageCrew to process the current page."""
        if self.state.current_page_index >= self.state.max_pages:
            logger.warning("Max pages reached, stopping")
            self.state.overall_status = "PARTIAL"
            return "max_pages_reached"

        logger.info(
            f"Processing page {self.state.current_page_index + 1} "
            f"(retry {self.state.retry_count})"
        )

        page = self._browser_manager.page
        crew = build_page_crew(page, self._settings)

        page_start = time.time()
        result = crew.kickoff(
            inputs={
                "test_data": json.dumps(self.state.test_case_data),
                "consumed_fields": json.dumps(self.state.consumed_fields),
                "validation_errors": json.dumps(self.state.validation_errors),
            }
        )
        page_duration = round(time.time() - page_start, 2)

        # Extract per-task timing from CrewAI's built-in instrumentation
        task_labels = ["analyze", "map", "fill", "verify"]
        task_durations: dict[str, float] = {}
        for i, task in enumerate(crew.tasks):
            label = task_labels[i] if i < len(task_labels) else f"task_{i}"
            dur = getattr(task, "execution_duration", None)
            if dur is not None:
                task_durations[label] = round(dur, 2)

        # Extract token usage from CrewOutput
        token_usage: dict[str, int] = {}
        if hasattr(result, "token_usage") and result.token_usage:
            try:
                token_usage = result.token_usage.model_dump()
            except Exception:
                token_usage = {}

        logger.info(
            f"Page {self.state.current_page_index + 1} completed in {page_duration}s | "
            f"Tasks: {task_durations} | Tokens: {token_usage.get('total_tokens', '?')}"
        )

        self._update_state_from_crew_result(
            result,
            page_duration=page_duration,
            task_durations=task_durations,
            token_usage=token_usage,
        )
        return "crew_done"

    def _update_state_from_crew_result(
        self,
        result: Any,
        page_duration: float = 0.0,
        task_durations: dict[str, float] | None = None,
        token_usage: dict[str, int] | None = None,
    ) -> None:
        """Parse crew output and update flow state."""
        raw = str(result)
        logger.debug(f"Crew result (raw): {raw[:500]}")

        # Try to parse the verification result from the last task output
        try:
            # The crew result might be JSON or text - try to extract JSON
            parsed = self._extract_json(raw)

            self.state.verification_passed = parsed.get("passed", False)
            self.state.current_page_id = parsed.get(
                "new_page_id", f"page_{self.state.current_page_index}"
            )

            errors = parsed.get("validation_errors", [])
            self.state.validation_errors = [
                e.get("message", str(e)) if isinstance(e, dict) else str(e)
                for e in errors
            ]

            screenshot = parsed.get("screenshot_path", "")
            if screenshot:
                self.state.screenshots.append(screenshot)

            # Track consumed fields
            consumed = parsed.get("consumed_keys", [])
            self.state.consumed_fields.extend(consumed)

            is_final = parsed.get("is_final_page", False)
            if is_final:
                self.state.current_page_id = "completion"

            field_results = parsed.get("field_results", [])

        except Exception as e:
            logger.warning(f"Could not parse crew result as JSON: {e}")
            # Heuristic: if no errors mentioned, assume passed
            raw_lower = raw.lower()
            if "error" in raw_lower or "fail" in raw_lower:
                self.state.verification_passed = False
                self.state.validation_errors = ["Could not parse verification result"]
            else:
                self.state.verification_passed = True
            field_results = []

        # Record page result
        self.state.page_results.append(
            {
                "page_index": self.state.current_page_index,
                "page_id": self.state.current_page_id,
                "verification_passed": self.state.verification_passed,
                "validation_errors": self.state.validation_errors,
                "retry_count": self.state.retry_count,
                "field_results": field_results,
                "duration_seconds": page_duration,
                "task_durations": task_durations or {},
                "token_usage": token_usage or {},
            }
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Try to extract a JSON object from text that may contain other content."""
        # Try the whole string
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find the last JSON block (verification task is the last output)
        depth = 0
        start = -1
        for i in range(len(text) - 1, -1, -1):
            if text[i] == "}":
                if depth == 0:
                    end = i
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    start = i
                    break
        if start >= 0:
            return json.loads(text[start : end + 1])
        raise ValueError("No JSON object found in text")

    @listen("complete")
    def generate_report(self) -> dict:
        """Generate the final test report and clean up."""
        duration = time.time() - self.state.start_time

        # Determine overall status
        if not self.state.page_results:
            self.state.overall_status = "FAIL"
        elif all(p.get("verification_passed") for p in self.state.page_results):
            self.state.overall_status = "PASS"
        elif any(p.get("verification_passed") for p in self.state.page_results):
            self.state.overall_status = "PARTIAL"
        else:
            self.state.overall_status = "FAIL"

        pages = []
        for pr in self.state.page_results:
            field_results = []
            for fr in pr.get("field_results", []):
                try:
                    field_results.append(
                        FieldActionResult(
                            field_id=fr.get("field_id", ""),
                            selector=fr.get("selector", ""),
                            value=fr.get("value", ""),
                            status=fr.get("status", ""),
                            error_message=fr.get("error_message", ""),
                        )
                    )
                except Exception:
                    pass
            pages.append(
                PageResult(
                    page_index=pr.get("page_index", 0),
                    page_id=pr.get("page_id", "unknown"),
                    fields_filled=field_results,
                    verification_passed=pr.get("verification_passed", False),
                    validation_errors=pr.get("validation_errors", []),
                    retry_count=pr.get("retry_count", 0),
                    duration_seconds=pr.get("duration_seconds", 0.0),
                    task_durations=pr.get("task_durations", {}),
                    token_usage=pr.get("token_usage", {}),
                )
            )

        # Aggregate token usage across all pages
        total_tokens = sum(
            pr.get("token_usage", {}).get("total_tokens", 0)
            for pr in self.state.page_results
        )
        prompt_tokens = sum(
            pr.get("token_usage", {}).get("prompt_tokens", 0)
            for pr in self.state.page_results
        )
        completion_tokens = sum(
            pr.get("token_usage", {}).get("completion_tokens", 0)
            for pr in self.state.page_results
        )

        report = TestReport(
            test_case_id=self.state.test_case_id,
            url=self.state.target_url,
            overall_status=self.state.overall_status,
            total_pages=self.state.current_page_index + 1,
            pages_completed=sum(1 for p in pages if p.verification_passed),
            pages=pages,
            screenshots=self.state.screenshots,
            start_time=time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(self.state.start_time),
            ),
            end_time=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=round(duration, 2),
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # Save reports
        report_dict = report.model_dump()
        json_path = save_json_report(report_dict, self.state.test_case_id)
        html_path = save_html_report(report_dict, self.state.test_case_id)

        logger.info(
            f"Test complete: {self.state.overall_status} | "
            f"Pages: {report.pages_completed}/{report.total_pages} | "
            f"Duration: {report.duration_seconds}s"
        )
        logger.info(f"Reports: {json_path}, {html_path}")

        # Cleanup browser
        if self._browser_manager:
            self._browser_manager.close()

        return report_dict
