"""End-to-end tests using real Flask server and LLM API.

Run with: pytest -m e2e -v
Requires: valid OPENAI_API_KEY in .env, Flask test server
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time

import pytest
import requests

from src.config import get_settings
from src.flow.form_test_flow import FormTestFlow
from src.parsers.parser_factory import parse_test_file


@pytest.fixture(scope="module")
def flask_server():
    """Start Flask test server and wait for it to be ready."""
    server_proc = subprocess.Popen(
        ["python", "test_server/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )

    # Wait for server to be ready (max 10 seconds)
    base_url = "http://localhost:5555"
    for _ in range(20):
        try:
            resp = requests.get(f"{base_url}/form/step1", timeout=1)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.5)
    else:
        server_proc.terminate()
        pytest.fail("Flask test server failed to start within 10 seconds")

    yield base_url

    # Cleanup
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()


@pytest.mark.e2e
class TestE2EFormFlow:
    """End-to-end test: parse → browser → agents → report."""

    @pytest.mark.timeout(300)  # 5 minute timeout
    def test_multi_step_insurance_form(self, flask_server, tmp_path):
        """Run the 3-step insurance form test with real LLM."""
        url = f"{flask_server}/form"
        test_file = "test_data/multi_step_form.json"

        settings = get_settings()
        # Override BROWSER_PROXY to empty for local testing
        settings.browser_proxy = ""

        test_cases = parse_test_file(test_file, url, settings)
        assert len(test_cases) >= 1

        tc = test_cases[0]

        flow = FormTestFlow(settings=settings)
        flow.state.test_input_path = test_file
        flow.state.target_url = url
        flow.state.max_pages = 50
        flow.state.max_retries = 3
        flow._load_test_case(tc)

        result = flow.kickoff()

        # Basic assertions
        assert isinstance(result, dict)
        assert "test_case_id" in result
        assert result["test_case_id"] == "TC010_multi_step_insurance"
        assert result["url"] == url

        # Status should be one of the valid statuses
        assert result["overall_status"] in (
            "PASS",
            "PASS_WITH_RETRIES",
            "PARTIAL",
            "FAIL",
            "ERROR",
        )

        # Should have processed at least one page
        assert len(result["pages"]) >= 1
        assert result["duration_seconds"] > 0

        # Verify reports were generated
        json_report = f"reports/{tc.test_id}_report.json"
        html_report = f"reports/{tc.test_id}_report.html"
        assert os.path.exists(json_report), f"JSON report not found: {json_report}"
        assert os.path.exists(html_report), f"HTML report not found: {html_report}"

        # Verify JSON report is valid
        with open(json_report) as f:
            report_data = json.load(f)
        assert report_data["test_case_id"] == "TC010_multi_step_insurance"

        # Log results for visibility
        print(f"\n--- E2E Test Results ---")
        print(f"Status: {result['overall_status']}")
        print(f"Pages processed: {len(result['pages'])}")
        print(f"Duration: {result['duration_seconds']:.1f}s")
        print(f"Total tokens: {result.get('total_tokens', 'N/A')}")
        for i, page in enumerate(result["pages"]):
            print(
                f"  Page {i}: {page['page_id']} | "
                f"passed={page['verification_passed']} | "
                f"fields={len(page['fields_filled'])}"
            )
