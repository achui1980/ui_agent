# Code Structure

**AI-DLC Stage:** Inception / Reverse Engineering
**Date:** 2026-02-28
**Project:** UI Agent - AI-powered web form testing system

---

## Overview

The UI Agent is a Python 3.11+ project that uses CrewAI (multi-agent orchestration) and Playwright (browser automation) to test multi-step web forms. Four cooperating LLM agents analyze, map, fill, and verify form pages given structured or natural language test data.

The project follows a clean layered architecture: CLI entry point -> Flow state machine -> Crew per page -> Agents with Tools -> Browser via Playwright.

---

## Directory Tree

```
ui_agent/
├── src/                          # Application source code
│   ├── __init__.py
│   ├── main.py                   # CLI entry point (Click commands)
│   ├── config.py                 # Pydantic Settings (reads .env)
│   ├── agents/                   # CrewAI Agent factory functions (4 agents)
│   │   ├── __init__.py
│   │   ├── page_analyzer.py      # DOM + VLM visual analysis agent
│   │   ├── field_mapper.py       # Semantic field matching agent (LLM only)
│   │   ├── form_filler.py        # Fill/select/click actions agent
│   │   └── result_verifier.py    # Post-submit verification agent
│   ├── browser/                  # Playwright lifecycle management
│   │   ├── __init__.py
│   │   └── browser_manager.py    # Browser start/navigate/close
│   ├── flow/                     # CrewAI Flow state machine
│   │   ├── __init__.py
│   │   ├── form_test_flow.py     # FormTestFlow state machine + FormTestState
│   │   └── page_crew.py          # 4-agent Crew builder per page
│   ├── models/                   # Pydantic data models
│   │   ├── __init__.py           # Re-exports: TestCase, FieldActionResult, PageResult, TestReport
│   │   ├── test_case.py          # TestCase model
│   │   ├── page_result.py        # FieldActionResult, PageResult models
│   │   └── report.py             # TestReport model
│   ├── parsers/                  # Test file parsers (JSON/YAML/CSV/Excel/NL)
│   │   ├── __init__.py
│   │   ├── parser_factory.py     # Dispatch by file extension
│   │   ├── json_parser.py        # JSON structured + flat format
│   │   ├── yaml_parser.py        # YAML structured + flat format
│   │   ├── csv_parser.py         # CSV with header row
│   │   ├── excel_parser.py       # Excel (.xlsx/.xls) with header row
│   │   └── nl_parser.py          # LLM-powered natural language parsing
│   ├── reporting/                # Report generators
│   │   ├── __init__.py
│   │   ├── json_report.py        # JSON report output
│   │   └── html_report.py        # Jinja2 HTML report output
│   ├── tools/                    # CrewAI Tool wrappers (10 tools)
│   │   ├── __init__.py           # Re-exports all 10 tool classes
│   │   ├── screenshot_tool.py         # Page screenshot capture
│   │   ├── screenshot_analysis_tool.py # VLM-powered visual analysis
│   │   ├── dom_extractor_tool.py      # DOM form element extraction
│   │   ├── fill_input_tool.py         # Text input filling
│   │   ├── select_option_tool.py      # Dropdown selection (native + react-select + generic)
│   │   ├── checkbox_tool.py           # Checkbox/radio toggle
│   │   ├── click_button_tool.py       # Button clicking with navigation wait
│   │   ├── date_picker_tool.py        # Date picker filling (3 strategies)
│   │   ├── upload_file_tool.py        # File upload
│   │   └── validation_error_tool.py   # Validation error extraction
│   └── utils/                    # Utility modules
│       ├── __init__.py
│       └── logging.py            # Loguru setup (stderr + file rotation)
├── tests/                        # pytest test suite (mirrors src/ structure)
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures: settings, sample_test_data, test_data_dir
│   ├── test_cli.py               # CLI command tests
│   ├── test_config.py            # Config/Settings tests
│   ├── test_flow/                # Flow state machine tests
│   │   ├── __init__.py
│   │   └── test_flow.py
│   ├── test_parsers/             # Parser tests (JSON, YAML, CSV, Excel, NL)
│   │   ├── __init__.py
│   │   └── test_parsers.py
│   ├── test_reporting/           # Report generator tests
│   │   ├── __init__.py
│   │   └── test_reporting.py
│   └── test_tools/               # Tool wrapper tests (mocked Playwright Page)
│       ├── __init__.py
│       └── test_tools.py
├── templates/
│   └── report.html               # Jinja2 HTML report template (170 lines)
├── test_data/                    # Sample test case files
│   ├── sample_test.json          # JSON format sample
│   ├── sample_test.yaml          # YAML format sample
│   ├── sample_test.csv           # CSV format sample
│   ├── demoqa_practice_form.json # DemoQA practice form test data
│   ├── multi_step_form.json      # Multi-step form test data
│   ├── multi_step_registration.yaml # Multi-step registration YAML
│   └── demoqa_nl_test.txt        # Natural language test description
├── test_server/
│   └── app.py                    # Flask 3-step insurance form for local testing
├── AGENTS.md                     # Comprehensive codebase guide
├── README.md                     # Project readme
├── .env.example                  # Example environment configuration
└── pyproject.toml                # Project metadata and dependencies
```

---

## Module Details

### `src/main.py` -- CLI Entry Point

The CLI is built with Click and exposes three commands:

- **`cli()`** -- Click group. Calls `setup_logging()` on every invocation.
- **`run(test_file, url, max_pages, max_retries)`** -- Full form test execution. For `.txt` (NL) files, creates a single `FormTestFlow` and lets the flow handle parsing. For other formats, parses test cases upfront via `parse_test_file()`, then loops over each test case creating a new `FormTestFlow` per case.
- **`validate(test_file, url)`** -- Parse-only validation. For `.txt` files, starts a browser to extract DOM page context before NL parsing, then displays parsed test cases. Cleans up browser in `finally` block.
- **`analyze(url, visual)`** -- Single-page analysis. Starts browser, runs `DOMExtractorTool`, `ScreenshotTool`, and optionally `ScreenshotAnalysisTool` (VLM). Displays results to stdout.

### `src/config.py` -- Configuration

- **`Settings(BaseSettings)`** -- Pydantic Settings class reading from `.env`. Fields: `openai_api_key`, `openai_api_base`, `https_proxy`, `llm_model` (default `gpt-5.2`), `vlm_model`, `llm_max_tokens`, `vlm_max_tokens`, `browser_headless`, `browser_timeout`, `browser_navigation_timeout`, `browser_viewport_width`, `browser_viewport_height`, `browser_proxy`, `awa_max_steps`, `awa_max_healing_attempts`, `awa_screenshot_dir`, `log_level`.
- **`get_settings()`** -- Factory function returning a fresh `Settings()` instance.

### `src/agents/` -- Agent Factory Functions

Each module exports a factory function following the pattern `create_<role>(page, llm, settings=None) -> Agent`.

| Module | Factory | Role | Tools Used |
|--------|---------|------|------------|
| `page_analyzer.py` | `create_page_analyzer(page, llm, settings)` | Page Analyzer | DOMExtractorTool, ScreenshotTool, ScreenshotAnalysisTool (conditional on VLM config) |
| `field_mapper.py` | `create_field_mapper(llm)` | Field Mapper | None (pure LLM reasoning) |
| `form_filler.py` | `create_form_filler(page, llm)` | Form Filler | FillInputTool, SelectOptionTool, CheckboxTool, ClickButtonTool, DatePickerTool, UploadFileTool |
| `result_verifier.py` | `create_result_verifier(page, llm, settings)` | Result Verifier | ScreenshotTool, GetValidationErrorsTool |

All agents set `verbose=True` for detailed CrewAI logging.

### `src/browser/browser_manager.py` -- Browser Lifecycle

- **`BrowserManager`** -- Manages the full Playwright lifecycle. Holds `_playwright`, `_browser`, `_context`, `_page` as private state.
  - `start() -> Page` -- Launches Chromium with configured headless mode, proxy, viewport, and timeouts. Returns the `Page` instance.
  - `navigate(url)` -- Navigates to URL with `wait_until="networkidle"`.
  - `close()` -- Tears down context, browser, and playwright in order. Nulls all references.
  - `page` property -- Returns `_page` or raises `RuntimeError` if not started.

### `src/flow/form_test_flow.py` -- Flow State Machine

- **`FormTestState(BaseModel)`** -- Flow global state with fields for input paths, parsed test case data, page loop state (index, consumed fields, results, retries), and final report state (status, screenshots, timing).
- **`FormTestFlow(Flow[FormTestState])`** -- CrewAI Flow subclass orchestrating the full test run.
  - `__init__(settings)` -- Initializes settings and connects config values (`awa_max_steps`, `awa_max_healing_attempts`) to state.
  - `parse_test_case()` -- `@start()` method. Detects NL vs structured input. Returns `"parsed"` or `"needs_page_analysis"`.
  - `route_after_parse()` -- `@router(parse_test_case)`. Routes to `"open_browser"` or `"pre_analyze"`.
  - `pre_analyze_page()` -- `@listen("pre_analyze")`. Opens browser, extracts DOM, parses NL with page context, then calls `_run_page_loop()`.
  - `open_browser_and_navigate()` -- `@listen("open_browser")`. Starts browser (if not already) and calls `_run_page_loop()`.
  - `_run_page_loop()` -- Unified page loop engine. Drives `process_page()` in a while-loop with retry/advance/complete logic.
  - `process_page()` -- Builds and kicks off a `PageCrew`, extracts timing and token usage, updates state.
  - `_update_state_from_crew_result(result, ...)` -- Parses JSON from crew output, extracts verification status, validation errors, consumed fields, field results.
  - `_extract_json(text)` -- Static method. Tries full JSON parse, then scans for last `{}` block.
  - `generate_report()` -- `@listen("complete")`. Computes overall status, builds `TestReport`, saves JSON + HTML reports, cleans up browser.
  - `_load_test_case(tc)` -- Loads a parsed `TestCase` into flow state.

### `src/flow/page_crew.py` -- Crew Builder

- **`build_page_crew(page, settings) -> Crew`** -- Constructs a 4-agent, 4-task sequential `Crew` for processing one form page. Creates LLM instance, instantiates all 4 agents, defines tasks with context chaining:
  1. **analyze_task** -- DOM extraction + visual analysis + screenshot (PageAnalyzer)
  2. **map_task** -- Map test data to page fields, context from analyze_task (FieldMapper)
  3. **fill_task** -- Execute form actions, context from map_task (FormFiller)
  4. **verify_task** -- Post-submission verification, context from analyze_task + fill_task (ResultVerifier)

### `src/models/` -- Data Models

| Model | File | Fields |
|-------|------|--------|
| `TestCase` | `test_case.py` | `test_id: str`, `url: str`, `data: dict[str, str]`, `description: str = ""`, `expected_outcome: str = "success"` |
| `FieldActionResult` | `page_result.py` | `field_id: str`, `selector: str`, `value: str`, `status: str`, `error_message: str = ""` |
| `PageResult` | `page_result.py` | `page_index: int`, `page_id: str`, `fields_filled: list[FieldActionResult]`, `verification_passed: bool`, `validation_errors: list[str]`, `retry_count: int`, `screenshot_path: str`, `duration_seconds: float`, `task_durations: dict[str, float]`, `token_usage: dict[str, int]` |
| `TestReport` | `report.py` | `test_case_id: str`, `url: str`, `overall_status: str`, `total_pages: int`, `pages_completed: int`, `pages: list[PageResult]`, `screenshots: list[str]`, `start_time: str`, `end_time: str`, `duration_seconds: float`, `total_tokens: int`, `prompt_tokens: int`, `completion_tokens: int` |

### `src/parsers/` -- Test File Parsers

- **`parser_factory.py`** -- `parse_test_file(path, url, settings, page_context) -> list[TestCase]`. Dispatches by extension: `.xlsx`/`.xls` -> `parse_excel`, `.csv` -> `parse_csv`, `.json` -> `parse_json`, `.yaml`/`.yml` -> `parse_yaml`, `.txt` -> `parse_natural_language`. Raises `ValueError` for unsupported formats or missing NL requirements.
- **`json_parser.py`** -- `parse_json(path, url) -> list[TestCase]`. Supports structured format (objects with `data` dict) and flat format (whole object as field->value). Single object auto-wrapped to list.
- **`yaml_parser.py`** -- `parse_yaml(path, url) -> list[TestCase]`. Same structure as JSON parser, uses `yaml.safe_load`.
- **`csv_parser.py`** -- `parse_csv(path, url) -> list[TestCase]`. Uses `csv.DictReader`. Separates meta keys (`test_id`, `url`, `description`, `expected_outcome`) from data keys. Each row is one test case.
- **`excel_parser.py`** -- `parse_excel(path, url) -> list[TestCase]`. Uses `openpyxl`. First row = headers, subsequent rows = test cases. Same meta/data key separation as CSV.
- **`nl_parser.py`** -- `parse_natural_language(path, url, settings, page_context) -> list[TestCase]`. Two-stage: builds field description from DOM context via `_build_field_description()`, then sends LLM prompt with form fields + user text. Extracts JSON from LLM response, strips markdown fences. Requires `page_context` (raises `ValueError` without it).

### `src/reporting/` -- Report Generators

- **`json_report.py`** -- `save_json_report(report, test_case_id) -> str`. Writes to `reports/{test_case_id}_report.json`.
- **`html_report.py`** -- `save_html_report(report, test_case_id) -> str`. Renders `templates/report.html` via Jinja2 with autoescaping. Writes to `reports/{test_case_id}_report.html`.

### `src/tools/` -- CrewAI Tool Wrappers

10 tool classes, all following the BaseTool pattern with `_run()` method and self-healing fallbacks:

| Tool | Name | Input Schema | Description |
|------|------|-------------|-------------|
| `ScreenshotTool` | "Screenshot" | `ScreenshotInput(save_path)` | Full-page screenshot, auto-generates timestamped filename |
| `ScreenshotAnalysisTool` | "Screenshot Analysis" | `ScreenshotAnalysisInput(question)` | VLM-powered: takes screenshot, base64-encodes, sends to OpenAI vision API |
| `DOMExtractorTool` | "DOM Extractor" | `DOMExtractorInput()` (no params) | JavaScript `page.evaluate()` to extract all form fields, buttons, step indicators, errors |
| `FillInputTool` | "Fill Input" | `FillInputInput(selector, value)` | Primary: `locator.fill()` + Escape. Fallback: `press_sequentially()` with delay |
| `SelectOptionTool` | "Select Option" | `SelectOptionInput(selector, label, value)` | 3 strategies: native `<select>`, react-select (type + click option), generic dropdown |
| `CheckboxTool` | "Checkbox Toggle" | `CheckboxInput(selector, check)` | Primary: `check()`/`uncheck()`. Fallbacks: label click, force click. Pre-dismisses overlays |
| `ClickButtonTool` | "Click Button" | `ClickButtonInput(selector, wait_for_navigation)` | Primary: Playwright click + networkidle wait. Fallback: JS `el.click()` |
| `DatePickerTool` | "Date Picker" | `DatePickerInput(selector, value)` | 3 strategies: triple-click + type + Escape, direct fill, JS value injection with events |
| `UploadFileTool` | "Upload File" | `UploadFileInput(selector, file_path)` | Validates file exists, uses `set_input_files()`. No fallback strategy |
| `GetValidationErrorsTool` | "Get Validation Errors" | `GetValidationErrorsInput()` (no params) | JavaScript extraction: CSS class-based + HTML5 validity. Deduplicates by message |

### `src/utils/logging.py` -- Logging Setup

- **`setup_logging()`** -- Configures Loguru with two sinks: stderr (configurable level, colored format) and file (`reports/ui_agent.log`, DEBUG level, 10MB rotation, 7-day retention).

### `templates/report.html` -- Jinja2 Report Template

HTML report with CSS styling. Includes:
- Summary section with status badge (PASS/FAIL/PARTIAL), URL, timing, token counts
- Per-page cards with task timing bars (analyze/map/fill/verify), field results table, validation errors
- Responsive grid layout

### `test_server/app.py` -- Flask Test Server

A Flask application serving a 3-step insurance form for local integration testing.

### `test_data/` -- Sample Test Files

7 sample files in various formats: JSON (structured), JSON (flat), YAML, CSV, multi-step JSON, multi-step YAML, and NL text.

---

## Naming Conventions

| Category | Convention | Examples |
|----------|-----------|----------|
| **Files** | `snake_case.py` | `form_test_flow.py`, `dom_extractor_tool.py`, `page_result.py` |
| **Classes** | `PascalCase` | `FormTestFlow`, `FillInputTool`, `BrowserManager`, `TestCase` |
| **Functions/methods** | `snake_case` | `parse_test_file`, `create_page_analyzer`, `setup_logging` |
| **Agent factories** | `create_<role>(page, llm, settings=None) -> Agent` | `create_page_analyzer`, `create_form_filler` |
| **Tool classes** | `<Action>Tool` + `<Action>Input` | `FillInputTool` / `FillInputInput`, `DatePickerTool` / `DatePickerInput` |
| **Private members** | `_` prefix | `self._browser`, `self._settings`, `self._page` |
| **Constants** | Pydantic `Field(default=...)` | Not module-level `UPPER_CASE`; config fields in `Settings` |
| **Test classes** | `Test<ClassName>` | `TestFillInputTool`, `TestFormTestFlow` |
| **Test methods** | `test_<scenario>` | `test_fill_success`, `test_parse_json_structured` |

## Import Conventions

- All modules start with `from __future__ import annotations` (PEP 604 unions).
- Import order: stdlib -> third-party -> local (`src.*`). Blank line between groups.
- Absolute imports from project root: `from src.models import TestCase`.
- Exception: parsers use relative imports within the package: `from .json_parser import parse_json`.

## Formatting

- 4-space indentation, no tabs
- Max line length ~88 chars (Black-compatible)
- Trailing commas in multi-line collections and signatures
- Double quotes for all strings
