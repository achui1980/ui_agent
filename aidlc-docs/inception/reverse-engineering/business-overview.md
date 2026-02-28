# Business Overview - UI Agent

**AI-DLC Stage**: Inception / Reverse Engineering
**Generated**: 2026-02-28
**Project**: UI Agent - AI-Powered Web Form Testing System

---

## 1. Business Context

UI Agent is an AI-powered automated testing system designed for complex, multi-step web forms typical of insurance and financial applications. These forms present unique challenges: multi-page wizards with conditional fields, cascading dropdowns (e.g., state -> city), date pickers, file uploads, and dynamic validation. Manual testing of such forms is slow, error-prone, and expensive.

The system uses four cooperating LLM agents (orchestrated by CrewAI) to analyze, understand, fill, and verify web forms -- replacing the brittle selector-based approach of traditional automation with intelligent, adaptive form interaction. Test data can be provided in structured formats (JSON, YAML, CSV, Excel) or as free-form natural language descriptions.

### Target Domain

- Insurance application forms (multi-step wizards)
- Financial services onboarding forms
- Any complex web form with multi-page navigation, dropdowns, date pickers, file uploads, and validation logic

### Key Value Proposition

- **Semantic understanding**: LLM agents match test data to form fields by meaning, not by fragile CSS selectors hardcoded in test scripts
- **Self-healing**: When a primary interaction strategy fails (e.g., a `fill()` call throws), tools automatically try fallback strategies and report `HEALED` status
- **Visual analysis**: Optional VLM (Vision Language Model) analysis identifies UI components that DOM inspection alone may misclassify (e.g., a text input that is actually a react-select dropdown)
- **Natural language input**: QA engineers can describe test data in plain English instead of writing structured JSON

---

## 2. Core Business Transactions

### 2.1 Form Test Execution (`ui-agent run`)

The primary transaction. End-to-end automated form filling and verification.

**Flow**:
1. Parse test data file (JSON/YAML/CSV/Excel/NL) into `TestCase` objects
2. Open browser (Playwright Chromium) and navigate to target URL
3. For each form page (up to `max_pages`, default 50):
   a. **Page Analyzer** agent extracts DOM fields + takes screenshot + optional VLM analysis
   b. **Field Mapper** agent semantically matches test data keys to discovered form fields
   c. **Form Filler** agent executes fill/select/click/upload actions via browser tools
   d. **Result Verifier** agent checks for validation errors, page transitions, or completion
4. If verification fails, retry the page (up to `max_retries`, default 3)
5. If verification passes, advance to the next page
6. Generate JSON + HTML reports with per-field results, timing, token usage, and screenshots

**Inputs**: Test file path, target URL, max pages, max retries
**Outputs**: `TestReport` (JSON + HTML) with overall status (PASS/FAIL/PARTIAL)

### 2.2 Test File Validation (`ui-agent validate`)

Parse and validate a test case file without executing any browser actions.

**Flow**:
1. Detect file format by extension
2. For `.txt` (NL) files: start browser, extract DOM fields, then use LLM to parse NL with page context
3. For structured files: parse directly
4. Display parsed test cases (ID, URL, field count, data, expected outcome)

**Inputs**: Test file path, optional URL (required for `.txt`)
**Outputs**: Console display of parsed test cases

### 2.3 Page Analysis (`ui-agent analyze`)

Extract and display form field information from a target URL without filling any fields.

**Flow**:
1. Open browser, navigate to URL
2. Extract DOM fields (selectors, types, labels, options, buttons, errors)
3. Take screenshot
4. Optionally run VLM visual analysis to identify custom UI components

**Inputs**: Target URL, visual flag (default: enabled)
**Outputs**: Console display of DOM extraction JSON, screenshot path, VLM analysis

### 2.4 Natural Language Test Parsing (Two-Stage)

Converts free-form English test descriptions into structured `TestCase` objects.

**Stage 1 - Page Pre-Analysis**:
1. Flow detects `.txt` extension, routes to `pre_analyze_page()`
2. Opens browser, navigates to target URL
3. Runs `DOMExtractorTool` to extract field IDs, labels, types, options
4. Stores result as `page_context`

**Stage 2 - Context-Aware NL Parsing**:
1. NL parser receives `page_context` and builds a field-aware LLM prompt
2. Prompt includes the actual form field names, types, and options from the DOM
3. LLM maps natural language descriptions to form field keys
4. Parser builds `preferred_key` suggestions from DOM labels (e.g., `first_name` instead of `firstNameInput`)
5. Returns structured `TestCase` with `data: dict[str, str]`

**Key design decisions**:
- NL files require a URL (the `--url` flag is mandatory)
- No hardcoded date formats -- the LLM infers format from page context
- The NL parser uses the CrewAI `LLM` class directly (not an agent) for structured extraction

---

## 3. Multi-Agent Collaboration

Four agents work sequentially per form page, each building on the previous agent's output via CrewAI's task context chaining:

| Agent | Role | Tools | Output |
|---|---|---|---|
| **Page Analyzer** | DOM extraction + VLM visual analysis + screenshot | DOMExtractorTool, ScreenshotTool, ScreenshotAnalysisTool | JSON: fields, buttons, errors, visual notes |
| **Field Mapper** | Semantic matching of test data to page fields | None (pure LLM reasoning) | JSON: mappings, unmapped fields, consumed keys |
| **Form Filler** | Execute fill/select/click/upload actions | FillInputTool, SelectOptionTool, CheckboxTool, ClickButtonTool, DatePickerTool, UploadFileTool | JSON: field results, submit status |
| **Result Verifier** | Verify submission, detect errors/transitions | ScreenshotTool, GetValidationErrorsTool | JSON: passed, page transition, errors, is final page |

### Agent Interaction Pattern

```
Page Analyzer --> [context] --> Field Mapper --> [context] --> Form Filler --> [context] --> Result Verifier
                                                                                              |
                                                                     Result feeds back to Flow state
                                                                     (retry / next page / complete)
```

- The Field Mapper receives the Analyzer's field list as task context
- The Form Filler receives the Mapper's field-to-value mappings as context
- The Result Verifier receives both the Analyzer's original page state and the Filler's action results

---

## 4. Supported Input Formats

| Format | Extension | Parser Module | Notes |
|---|---|---|---|
| JSON | `.json` | `json_parser.py` | Single object or array of test cases |
| YAML | `.yaml`, `.yml` | `yaml_parser.py` | Same structure as JSON |
| CSV | `.csv` | `csv_parser.py` | One row per test case, headers are field names |
| Excel | `.xlsx`, `.xls` | `excel_parser.py` | Uses openpyxl, one row per test case |
| Natural Language | `.txt` | `nl_parser.py` | Requires URL, two-stage LLM parsing |

All parsers produce `list[TestCase]` where each `TestCase` contains:
- `test_id: str` -- unique identifier
- `url: str` -- target form URL
- `data: dict[str, str]` -- canonical field name to value mapping
- `description: str` -- human-readable summary
- `expected_outcome: str` -- "success" (default)

---

## 5. Self-Healing Pattern

Every browser tool follows a two-tier error handling strategy:

```
Primary Strategy
    |
    +-- SUCCESS --> return "SUCCESS: ..."
    |
    +-- Exception --> Fallback Strategy
                        |
                        +-- SUCCESS --> return "HEALED: ..."
                        |
                        +-- Exception --> return "FAILED: ..."
```

**Examples**:
- `FillInputTool`: Primary uses `locator.fill(value)`. Fallback uses `locator.press_sequentially(value, delay=50)` for inputs that reject programmatic `fill`.
- Tools that dismiss popups (`FillInputTool`, `CheckboxTool`) press `Escape` after actions to close autocomplete/datepicker overlays that could block subsequent interactions.
- Tools never raise exceptions to the agent -- they return status strings so the agent can decide how to proceed.

**Status values**:
- `SUCCESS` -- primary strategy worked
- `HEALED` -- primary failed but fallback succeeded
- `FAILED` -- both strategies failed, error message included

---

## 6. Report Generation

After all pages are processed, the Flow generates two report formats:

### JSON Report (`reports/{test_case_id}_report.json`)
Complete machine-readable report with:
- `test_case_id`, `url`, `overall_status` (PASS/FAIL/PARTIAL)
- `total_pages`, `pages_completed`
- Per-page results: `page_index`, `page_id`, `verification_passed`, `validation_errors`, `retry_count`
- Per-field results: `field_id`, `selector`, `value`, `status`, `error_message`
- Timing: `duration_seconds`, `task_durations` (per-agent: analyze/map/fill/verify)
- Token usage: `total_tokens`, `prompt_tokens`, `completion_tokens` (aggregated across all pages)
- `screenshots`: list of screenshot file paths
- `start_time`, `end_time`

### HTML Report (`reports/{test_case_id}_report.html`)
Human-readable report rendered from a Jinja2 template (`templates/report.html`) containing the same data in a visual format.

### Overall Status Logic
- **PASS**: All pages have `verification_passed = true`
- **PARTIAL**: Some pages passed, some failed
- **FAIL**: No pages passed, or no page results at all
