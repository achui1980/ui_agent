# API Documentation

**AI-DLC Stage:** Inception / Reverse Engineering
**Date:** 2026-02-28
**Project:** UI Agent - AI-powered web form testing system

---

## CLI API

The CLI is implemented with Click in `src/main.py` and installed as the `ui-agent` console script via `pyproject.toml`. All commands require the `ui_agent` conda environment to be activated first.

### `ui-agent run`

Full form test execution.

```
ui-agent run <test_file> --url <url> [--max-pages N] [--max-retries N]
```

**Arguments:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `test_file` | positional | Yes | -- | Path to test data file (.json, .yaml, .yml, .csv, .xlsx, .xls, .txt) |
| `--url`, `-u` | option | Yes | -- | Target form URL |
| `--max-pages` | option | No | 50 | Maximum pages to process before stopping |
| `--max-retries` | option | No | 3 | Maximum retries per page on verification failure |

**Behavior:**
1. For `.txt` (NL) files: Creates a single `FormTestFlow`, sets state, and calls `kickoff()`. The flow handles browser startup, DOM extraction, NL parsing, and form testing internally.
2. For all other formats: Parses test cases upfront via `parse_test_file()`. Loops over each test case, creating a new `FormTestFlow` per case. Each flow opens a fresh browser, processes all form pages, generates reports, and closes the browser.

**Output:**
- JSON report: `reports/{test_case_id}_report.json`
- HTML report: `reports/{test_case_id}_report.html`
- Screenshots: `reports/screenshots/page_{timestamp}.png`
- Logs: `reports/ui_agent.log` (DEBUG level, rotated at 10MB)
- Stdout: Progress logging with test case IDs and final status summary

**Exit behavior:** Does not set non-zero exit codes on test failure (logs only).

---

### `ui-agent validate`

Parse and validate a test case file without executing form tests.

```
ui-agent validate <test_file> [--url <url>]
```

**Arguments:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `test_file` | positional | Yes | -- | Path to test data file |
| `--url`, `-u` | option | Conditional | `""` | Target URL. **Required for `.txt` files** (NL parsing needs browser context) |

**Behavior:**
1. For `.txt` files: Validates that `--url` is provided. Starts a browser, navigates to the URL, extracts DOM fields via `DOMExtractorTool`, then parses the NL text with page context. Closes browser in `finally` block.
2. For other formats: Parses directly without browser.

**Output (stdout):**
```
Parsed N test case(s):

  ID: test_case_1
  URL: https://example.com/form
  Fields: 7
  Expected: success
  Description: Sample insurance form test
  Data: {
      "first_name": "John",
      "last_name": "Smith",
      ...
  }
```

**Exit codes:** Exits with code 1 if URL missing for `.txt` or if parsing fails.

---

### `ui-agent analyze`

Analyze a single page's form fields without filling.

```
ui-agent analyze <url> [--visual/--no-visual]
```

**Arguments:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | positional | Yes | -- | Page URL to analyze |
| `--visual/--no-visual` | flag | No | `--visual` | Enable/disable VLM visual analysis |

**Behavior:**
1. Starts browser, navigates to URL
2. Runs `DOMExtractorTool` -- extracts all form fields, buttons, step indicators, validation errors
3. Runs `ScreenshotTool` -- saves page screenshot
4. If `--visual` and `vlm_model` is configured: runs `ScreenshotAnalysisTool` -- VLM analysis of screenshot

**Output (stdout):**
```
=== DOM Extraction ===
{
  "fields": [...],
  "buttons": [...],
  "step_indicator": "Step 1 of 3",
  "existing_errors": [],
  "page_title": "Insurance Application",
  "url": "https://example.com/form"
}

SUCCESS: Screenshot saved to reports/screenshots/page_1709164800.png

=== Visual Analysis (VLM) ===
SUCCESS: Visual analysis of reports/screenshots/analysis_1709164800.png:

The page shows a multi-step insurance form...
```

---

## Environment Variables

All configuration is loaded from a `.env` file by `pydantic-settings` into `src/config.py:Settings`.

### LLM Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OPENAI_API_KEY` | str | `""` | API key for LLM and VLM calls |
| `OPENAI_API_BASE` | str | `""` | Custom API base URL (for proxies or alternative providers) |
| `HTTPS_PROXY` | str | `""` | HTTPS proxy for outbound requests |
| `LLM_MODEL` | str | `"gpt-5.2"` | Model name for text LLM (used by all 4 agents) |
| `VLM_MODEL` | str | `"gpt-5.2"` | Model name for vision LLM (used by ScreenshotAnalysisTool) |
| `LLM_MAX_TOKENS` | int | `4096` | Max tokens for text LLM responses |
| `VLM_MAX_TOKENS` | int | `1000` | Max tokens for VLM responses |

### Browser Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BROWSER_HEADLESS` | bool | `False` | Run browser in headless mode |
| `BROWSER_TIMEOUT` | int | `10000` | Default action timeout (ms) |
| `BROWSER_NAVIGATION_TIMEOUT` | int | `60000` | Navigation timeout (ms) |
| `BROWSER_VIEWPORT_WIDTH` | int | `1280` | Browser viewport width (px) |
| `BROWSER_VIEWPORT_HEIGHT` | int | `720` | Browser viewport height (px) |
| `BROWSER_PROXY` | str | `""` | Browser proxy server URL |

### Agent/Workflow Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AWA_MAX_STEPS` | int | `50` | Maximum pages to process per test run (maps to `max_pages` state) |
| `AWA_MAX_HEALING_ATTEMPTS` | int | `3` | Maximum retries per page (maps to `max_retries` state) |
| `AWA_SCREENSHOT_DIR` | str | `"reports/screenshots"` | Directory for saving screenshots |

### Logging Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | str | `"INFO"` | Stderr log level (DEBUG, INFO, WARNING, ERROR) |

---

## Test Data Formats

The system supports 6 input formats. All formats produce `list[TestCase]` where each `TestCase` has: `test_id`, `url`, `data` (dict of field_name -> value), `description`, `expected_outcome`.

### JSON -- Structured Format

```json
[
  {
    "test_id": "insurance_basic",
    "description": "Basic insurance form test",
    "expected_outcome": "success",
    "data": {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john@example.com",
      "date_of_birth": "01/15/1990"
    }
  }
]
```

A single object (not wrapped in array) is also accepted. Multiple objects in the array produce multiple test cases.

### JSON -- Flat Format

```json
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@example.com"
}
```

When no `data` key is present, the entire object is treated as field->value data. `test_id` is auto-generated as `json_1`, `json_2`, etc.

### YAML

```yaml
test_id: insurance_basic
description: Basic insurance form test
expected_outcome: success
data:
  first_name: John
  last_name: Smith
  email: john@example.com
```

Same structure as JSON. Supports both structured (with `data` key) and flat formats. Lists of objects produce multiple test cases.

### CSV

```csv
test_id,first_name,last_name,email,date_of_birth,expected_outcome
insurance_1,John,Smith,john@example.com,01/15/1990,success
insurance_2,Jane,Doe,jane@example.com,03/22/1985,success
```

First row is headers. Columns named `test_id`, `url`, `description`, `expected_outcome` are metadata; all others are data fields. Each data row is one test case. Empty values are skipped.

### Excel (.xlsx, .xls)

Same structure as CSV. First row is headers, subsequent rows are test cases. Uses `openpyxl` for reading. Same meta key separation. Requires `openpyxl` to be installed.

### Natural Language (.txt)

```
Fill out the insurance form for John Smith, born January 15, 1990.
Email is john@example.com, phone number 555-123-4567.
He lives in Illinois and is male.
```

**Requirements:** `--url` flag is mandatory. The system:
1. Opens browser and navigates to the target URL
2. Extracts DOM field info (labels, types, options) as `page_context`
3. Sends LLM prompt with form fields + user text
4. LLM returns structured JSON with `test_id`, `data`, `description`

Field keys are derived from form labels (snake_case) rather than raw DOM IDs. Date values are kept in natural format -- the downstream form filler agent handles format conversion.

---

## Internal API

### Flow API

```python
from src.flow.form_test_flow import FormTestFlow
from src.config import get_settings

settings = get_settings()
flow = FormTestFlow(settings=settings)
flow.state.test_input_path = "test.json"
flow.state.target_url = "https://example.com/form"
flow.state.max_pages = 50
flow.state.max_retries = 3
result = flow.kickoff()  # Returns dict (TestReport.model_dump())
```

### Parser API

```python
from src.parsers.parser_factory import parse_test_file
from src.config import get_settings

# Structured formats
test_cases = parse_test_file("test.json", "https://example.com", get_settings())

# NL format (requires page_context)
test_cases = parse_test_file("test.txt", "https://example.com", settings, page_context=dom_dict)
```

### Tool API

All tools follow this pattern:

```python
from src.tools.fill_input_tool import FillInputTool

tool = FillInputTool(page=playwright_page)
result = tool._run(selector="#first_name", value="John")
# result: "SUCCESS: Filled '#first_name' with 'John'"
#     or: "HEALED: Filled '#first_name' with slow typing"
#     or: "FAILED: Could not fill '#first_name': ..."
```

### Report API

```python
from src.reporting.json_report import save_json_report
from src.reporting.html_report import save_html_report

json_path = save_json_report(report_dict, "test_case_1")  # -> "reports/test_case_1_report.json"
html_path = save_html_report(report_dict, "test_case_1")  # -> "reports/test_case_1_report.html"
```
