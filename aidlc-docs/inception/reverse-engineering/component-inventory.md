# Component Inventory

**AI-DLC Stage:** Inception / Reverse Engineering
**Date:** 2026-02-28
**Project:** UI Agent - AI-powered web form testing system

---

## Summary

| Category | Count | Components |
|----------|-------|------------|
| Agents | 4 | PageAnalyzer, FieldMapper, FormFiller, ResultVerifier |
| Tools | 10 | Screenshot, ScreenshotAnalysis, DOMExtractor, FillInput, SelectOption, Checkbox, ClickButton, DatePicker, UploadFile, GetValidationErrors |
| Parsers | 5+1 | JSON, YAML, CSV, Excel, NL + ParserFactory |
| Models | 4 | TestCase, FieldActionResult, PageResult, TestReport |
| Reporters | 2 | JsonReport, HtmlReport |
| Flow | 2 | FormTestFlow, PageCrew |
| Browser | 1 | BrowserManager |
| Config | 1 | Settings + get_settings() |

---

## Agents (4)

### 1. Page Analyzer

| Property | Value |
|----------|-------|
| **Factory** | `create_page_analyzer(page, llm, settings)` |
| **File** | `src/agents/page_analyzer.py` |
| **Role** | "Page Analyzer" |
| **Responsibility** | Analyze the current form page: extract all fields with CSS selectors, labels, types, and options. Identify navigation buttons and validation errors. Combines DOM extraction with VLM visual analysis to detect custom components (react-select, date pickers). |
| **Tools** | `DOMExtractorTool`, `ScreenshotTool`, `ScreenshotAnalysisTool` (conditional -- only added when `settings.vlm_model` is configured) |
| **Inputs** | Playwright `Page` instance, CrewAI `LLM`, optional `Settings` |
| **Output** | JSON with `page_id`, `fields[]`, `nav_button`, `existing_errors[]`, `screenshot_path`, `visual_notes` |

### 2. Field Mapper

| Property | Value |
|----------|-------|
| **Factory** | `create_field_mapper(llm)` |
| **File** | `src/agents/field_mapper.py` |
| **Role** | "Field Mapper" |
| **Responsibility** | Semantically match test data field names to page form field labels. Handle name differences, value format conversions, date splitting, and field ordering for cascading dropdowns. |
| **Tools** | None (pure LLM reasoning) |
| **Inputs** | CrewAI `LLM` only (no page reference needed) |
| **Output** | JSON with `mappings[]` (field_id, selector, value, action_type, execution_order, wait_after_ms), `unmapped_fields[]`, `consumed_keys[]` |
| **Context** | Receives output from analyze_task |

### 3. Form Filler

| Property | Value |
|----------|-------|
| **Factory** | `create_form_filler(page, llm)` |
| **File** | `src/agents/form_filler.py` |
| **Role** | "Form Filler" |
| **Responsibility** | Execute form filling actions precisely according to field mapping. Process fields in execution order, handle cascading dropdowns with waits, click submit/next when done. Continue on per-field failures. |
| **Tools** | `FillInputTool`, `SelectOptionTool`, `CheckboxTool`, `ClickButtonTool`, `DatePickerTool`, `UploadFileTool` |
| **Inputs** | Playwright `Page` instance, CrewAI `LLM` |
| **Output** | JSON with `field_results[]` (field_id, selector, value, status, error_message), `submit_clicked`, `submit_error` |
| **Context** | Receives output from map_task |

### 4. Result Verifier

| Property | Value |
|----------|-------|
| **Factory** | `create_result_verifier(page, llm, settings)` |
| **File** | `src/agents/result_verifier.py` |
| **Role** | "Result Verifier" |
| **Responsibility** | Verify form submission results. Detect validation errors, confirm page transitions, identify completion pages with confirmation numbers or success messages. |
| **Tools** | `ScreenshotTool`, `GetValidationErrorsTool` |
| **Inputs** | Playwright `Page` instance, CrewAI `LLM`, optional `Settings` |
| **Output** | JSON with `passed`, `page_transitioned`, `new_page_id`, `is_final_page`, `validation_errors[]`, `screenshot_path` |
| **Context** | Receives output from analyze_task + fill_task |

---

## Tools (10)

All tools inherit from `crewai.tools.BaseTool` and follow a consistent pattern:
- Each tool has a `<Name>Input(BaseModel)` schema class and a `<Name>Tool(BaseTool)` class
- The `page: Any` field holds a Playwright `Page` instance (with `model_config = {"arbitrary_types_allowed": True}`)
- `_run()` returns status strings: `"SUCCESS: ..."`, `"HEALED: ..."`, or `"FAILED: ..."`
- Self-healing: primary strategy in outer try, fallback in inner try, `FAILED` in inner except

### 1. ScreenshotTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/screenshot_tool.py` |
| **Name** | "Screenshot" |
| **Input** | `save_path: str = ""` (optional; auto-generates timestamped name) |
| **Output** | `"SUCCESS: Screenshot saved to {path}"` or `"FAILED: ..."` |
| **Behavior** | Takes a full-page screenshot via `page.screenshot(full_page=True)`. Creates `screenshot_dir` if needed. |
| **Config** | `screenshot_dir: str = "reports/screenshots"` |
| **Fallback** | None |

### 2. ScreenshotAnalysisTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/screenshot_analysis_tool.py` |
| **Name** | "Screenshot Analysis" |
| **Input** | `question: str` (defaults to comprehensive form analysis prompt) |
| **Output** | `"SUCCESS: Visual analysis of {path}:\n\n{analysis}"` or `"HEALED: Screenshot saved but VLM failed"` or `"FAILED: ..."` |
| **Behavior** | Takes screenshot, base64-encodes it, sends to OpenAI vision API with a detailed prompt about form elements, custom components, errors, and layout. |
| **Config** | `vlm_model`, `vlm_api_key`, `vlm_api_base`, `vlm_max_tokens`, `screenshot_dir` |
| **Fallback** | If VLM call fails, returns HEALED with screenshot path, advises relying on DOM extraction |

### 3. DOMExtractorTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/dom_extractor_tool.py` |
| **Name** | "DOM Extractor" |
| **Input** | None (no parameters) |
| **Output** | JSON string with `fields[]`, `buttons[]`, `step_indicator`, `existing_errors[]`, `page_title`, `url` |
| **Behavior** | Executes JavaScript via `page.evaluate()` to query all `input`, `select`, `textarea`, `[role="combobox"]`, `[role="listbox"]` elements. Extracts tag, type, id, name, selector, label, required, visible, enabled, value, options, group. Also detects buttons (`button`, `input[type="submit"]`, `[role="button"]`, `a.btn`), step indicators (`[class*="step"]`, `[class*="progress"]`, `[class*="wizard"]`), and validation errors (`.error`, `.invalid`, `[role="alert"]`). Deduplicates by id/name. |
| **Fallback** | None (single try/except) |

### 4. FillInputTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/fill_input_tool.py` |
| **Name** | "Fill Input" |
| **Input** | `selector: str`, `value: str` |
| **Output** | `"SUCCESS: Filled '{selector}' with '{value}'"` or `"HEALED: Filled with slow typing"` or `"FAILED: ..."` |
| **Behavior** | Primary: `locator.fill(value)` then `press("Escape")` to dismiss popups, 200ms wait. |
| **Fallback** | Click, clear, `press_sequentially(value, delay=50)`, Escape, 200ms wait |

### 5. SelectOptionTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/select_option_tool.py` |
| **Name** | "Select Option" |
| **Input** | `selector: str`, `label: str = ""`, `value: str = ""` |
| **Output** | `"SUCCESS: ..."` or `"HEALED: ..."` or `"FAILED: ..."` |
| **Behavior** | Three-strategy approach: |
| **Strategy 1** | Native `<select>`: detect tag, use `select_option(label=...)` or `select_option(value=...)`. Fuzzy match fallback (case-insensitive substring). |
| **Strategy 2** | React-select: find input with `id*='react-select'` or `role='combobox'`, click container, type to filter, click matching option. Fallback: press Enter to select first filtered option. Last resort: type + Enter. |
| **Strategy 3** | Generic dropdown: click trigger to open, find option via `[role='option']`, `[role='listbox']`, or `li` with matching text. |

### 6. CheckboxTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/checkbox_tool.py` |
| **Name** | "Checkbox Toggle" |
| **Input** | `selector: str`, `check: bool = True` |
| **Output** | `"SUCCESS: Checked/Unchecked '{selector}'"` or `"HEALED: ..."` or `"FAILED: ..."` |
| **Behavior** | Pre-dismisses overlays with `Escape` key press. Primary: `locator.check()` or `locator.uncheck()`. |
| **Fallback 1** | Click associated `label[for='...']` |
| **Fallback 2** | Force-click the element directly |

### 7. ClickButtonTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/click_button_tool.py` |
| **Name** | "Click Button" |
| **Input** | `selector: str`, `wait_for_navigation: bool = True` |
| **Output** | `"SUCCESS: Clicked '{selector}'"` or `"HEALED: JS-clicked"` or `"FAILED: ..."` |
| **Behavior** | Primary: Playwright `locator.click()` + optional `wait_for_load_state("networkidle")` with 30s timeout. |
| **Fallback** | JavaScript `el.click()` via `eval_on_selector`, same navigation wait |

### 8. DatePickerTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/date_picker_tool.py` |
| **Name** | "Date Picker" |
| **Input** | `selector: str`, `value: str` (YYYY-MM-DD, MM/DD/YYYY, or 'DD Mon YYYY') |
| **Output** | `"SUCCESS: Date filled..."` or `"HEALED: ..."` or `"FAILED: ..."` |
| **Strategy 1** | Triple-click to select all, `press_sequentially(value, delay=50)`, Escape to dismiss calendar, 300ms wait. Works with react-datepicker. |
| **Strategy 2** | Direct `locator.fill(value)`. Works for native date inputs. |
| **Strategy 3** | JavaScript value injection: sets `value` via `HTMLInputElement.prototype.value` setter, dispatches `input`, `change`, `blur` events. |

### 9. UploadFileTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/upload_file_tool.py` |
| **Name** | "Upload File" |
| **Input** | `selector: str`, `file_path: str` |
| **Output** | `"SUCCESS: Uploaded '{file_path}' to '{selector}'"` or `"FAILED: ..."` |
| **Behavior** | Validates file exists with `os.path.isfile()`, then uses `locator.set_input_files(file_path)`. |
| **Fallback** | None |

### 10. GetValidationErrorsTool

| Property | Value |
|----------|-------|
| **File** | `src/tools/validation_error_tool.py` |
| **Name** | "Get Validation Errors" |
| **Input** | None (no parameters) |
| **Output** | JSON array string of `{message, field_selector, field_label}` objects |
| **Behavior** | Two-strategy JavaScript extraction: (1) CSS class-based (`.error`, `.invalid`, `[role="alert"]`, etc.) with associated field detection via closest `.form-group`/`.field-wrapper`. (2) HTML5 validity API (`checkValidity()` + `validationMessage`). Deduplicates by message text. |
| **Fallback** | None (single try/except) |

---

## Parsers (5 + 1 Factory)

### ParserFactory

| Property | Value |
|----------|-------|
| **File** | `src/parsers/parser_factory.py` |
| **Function** | `parse_test_file(path, url, settings=None, page_context=None) -> list[TestCase]` |
| **Responsibility** | Dispatch to the correct parser based on file extension. Validates NL requirements (settings + page_context). |
| **Extensions** | `.xlsx`/`.xls` -> Excel, `.csv` -> CSV, `.json` -> JSON, `.yaml`/`.yml` -> YAML, `.txt` -> NL |

### JSON Parser

| Property | Value |
|----------|-------|
| **File** | `src/parsers/json_parser.py` |
| **Function** | `parse_json(path, url) -> list[TestCase]` |
| **Formats** | Structured (with `data` key) and flat (whole object as data). Single object auto-wrapped. |

### YAML Parser

| Property | Value |
|----------|-------|
| **File** | `src/parsers/yaml_parser.py` |
| **Function** | `parse_yaml(path, url) -> list[TestCase]` |
| **Formats** | Same as JSON parser. Uses `yaml.safe_load`. |

### CSV Parser

| Property | Value |
|----------|-------|
| **File** | `src/parsers/csv_parser.py` |
| **Function** | `parse_csv(path, url) -> list[TestCase]` |
| **Formats** | Header row + data rows. Meta keys (`test_id`, `url`, `description`, `expected_outcome`) separated from data keys. Uses `csv.DictReader`. |

### Excel Parser

| Property | Value |
|----------|-------|
| **File** | `src/parsers/excel_parser.py` |
| **Function** | `parse_excel(path, url) -> list[TestCase]` |
| **Formats** | Same structure as CSV. Uses `openpyxl.load_workbook(read_only=True)`. Raises `ValueError` if fewer than 2 rows. |

### Natural Language Parser

| Property | Value |
|----------|-------|
| **File** | `src/parsers/nl_parser.py` |
| **Functions** | `parse_natural_language(path, url, settings, page_context) -> list[TestCase]`, `_build_field_description(fields) -> str` |
| **Responsibility** | Two-stage NL parsing. Builds field-aware LLM prompt from DOM context. LLM extracts structured key-value pairs matching actual form fields. Handles markdown fence stripping. |
| **Requirements** | `page_context` is mandatory (raises `ValueError` without it). `Settings` required for LLM configuration. |

---

## Models (4)

### TestCase

| Property | Value |
|----------|-------|
| **File** | `src/models/test_case.py` |
| **Fields** | `test_id: str`, `url: str`, `data: dict[str, str]`, `description: str = ""`, `expected_outcome: str = "success"` |
| **Responsibility** | Canonical representation of a single test case. `data` maps field names to values. |

### FieldActionResult

| Property | Value |
|----------|-------|
| **File** | `src/models/page_result.py` |
| **Fields** | `field_id: str`, `selector: str`, `value: str`, `status: str` (success/failed/healed), `error_message: str = ""` |
| **Responsibility** | Result of a single field fill action. |

### PageResult

| Property | Value |
|----------|-------|
| **File** | `src/models/page_result.py` |
| **Fields** | `page_index: int`, `page_id: str`, `fields_filled: list[FieldActionResult]`, `verification_passed: bool`, `validation_errors: list[str] = []`, `retry_count: int = 0`, `screenshot_path: str = ""`, `duration_seconds: float = 0.0`, `task_durations: dict[str, float] = {}`, `token_usage: dict[str, int] = {}` |
| **Responsibility** | Result of processing a single form page (including all retries). |

### TestReport

| Property | Value |
|----------|-------|
| **File** | `src/models/report.py` |
| **Fields** | `test_case_id: str`, `url: str`, `overall_status: str` (PASS/FAIL/PARTIAL), `total_pages: int`, `pages_completed: int`, `pages: list[PageResult]`, `screenshots: list[str]`, `start_time: str`, `end_time: str`, `duration_seconds: float`, `total_tokens: int = 0`, `prompt_tokens: int = 0`, `completion_tokens: int = 0` |
| **Responsibility** | Complete test run report with aggregate metrics. |

---

## Reporters (2)

### JSON Report

| Property | Value |
|----------|-------|
| **File** | `src/reporting/json_report.py` |
| **Function** | `save_json_report(report: dict, test_case_id: str) -> str` |
| **Output** | `reports/{test_case_id}_report.json` |
| **Behavior** | Creates `reports/` directory, writes JSON with indent=2, ensure_ascii=False. |

### HTML Report

| Property | Value |
|----------|-------|
| **File** | `src/reporting/html_report.py` |
| **Function** | `save_html_report(report: dict, test_case_id: str) -> str` |
| **Output** | `reports/{test_case_id}_report.html` |
| **Behavior** | Loads `templates/report.html` via Jinja2 `FileSystemLoader` with autoescaping. Renders with `report` context variable. |

---

## Flow Components (2)

### FormTestFlow

| Property | Value |
|----------|-------|
| **File** | `src/flow/form_test_flow.py` |
| **Class** | `FormTestFlow(Flow[FormTestState])` |
| **State** | `FormTestState(BaseModel)` -- 20+ fields tracking input, parsed test case, page loop state, and final result |
| **Responsibility** | Orchestrates the full test run as a CrewAI Flow state machine. Handles NL pre-analysis routing, page processing loop with retries, and final report generation. |
| **Key Methods** | `parse_test_case()` (@start), `route_after_parse()` (@router), `pre_analyze_page()` (@listen), `open_browser_and_navigate()` (@listen), `_run_page_loop()`, `process_page()`, `_update_state_from_crew_result()`, `generate_report()` (@listen), `_load_test_case()`, `_extract_json()` (static) |
| **Entry Point** | `flow.kickoff()` returns `dict` (TestReport serialized) |

### PageCrew (build_page_crew)

| Property | Value |
|----------|-------|
| **File** | `src/flow/page_crew.py` |
| **Function** | `build_page_crew(page: Page, settings: Settings) -> Crew` |
| **Responsibility** | Constructs a 4-agent sequential `Crew` for processing one form page. Creates LLM instance, instantiates agents, defines 4 tasks with context chaining. |
| **Tasks** | analyze -> map (context: analyze) -> fill (context: map) -> verify (context: analyze + fill) |
| **Process** | `Process.sequential` |

---

## Browser (1)

### BrowserManager

| Property | Value |
|----------|-------|
| **File** | `src/browser/browser_manager.py` |
| **Class** | `BrowserManager` |
| **Responsibility** | Manages the Playwright browser lifecycle: start, navigate, close. Configures headless mode, proxy, viewport, timeouts from Settings. |
| **Key Methods** | `start() -> Page`, `navigate(url: str) -> None`, `close() -> None` |
| **Properties** | `page: Page` (raises `RuntimeError` if not started) |
| **State** | `_playwright`, `_browser`, `_context`, `_page` (all private, nullable) |

---

## Config (1)

### Settings

| Property | Value |
|----------|-------|
| **File** | `src/config.py` |
| **Class** | `Settings(BaseSettings)` |
| **Responsibility** | Centralizes all configuration via `.env` file. 17 fields covering LLM, browser, agent workflow, and logging settings. |
| **Factory** | `get_settings() -> Settings` |
| **Model Config** | `env_file=".env"`, `env_file_encoding="utf-8"`, `extra="ignore"` |
