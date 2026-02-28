# Architecture - UI Agent

**AI-DLC Stage**: Inception / Reverse Engineering
**Generated**: 2026-02-28
**Project**: UI Agent - AI-Powered Web Form Testing System

---

## 1. System Architecture Overview

The system is organized into four layers, each with a clear responsibility boundary:

```
+------------------------------------------------------------------+
|                        CLI Layer (Click)                          |
|  main.py: run | validate | analyze                               |
+------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
+------------------------------------------------------------------+
|                   Flow Layer (CrewAI Flow)                        |
|  FormTestFlow: state machine with @start/@listen/@router         |
|  FormTestState: Pydantic model for accumulated state             |
+------------------------------------------------------------------+
         |
         v  (per page, in a loop)
+------------------------------------------------------------------+
|                   Crew Layer (CrewAI Crew)                        |
|  build_page_crew(): 4-agent sequential Crew per page             |
|  Agents: PageAnalyzer -> FieldMapper -> FormFiller -> Verifier   |
+------------------------------------------------------------------+
         |
         v  (agents invoke tools)
+------------------------------------------------------------------+
|                  Tool Layer (Playwright)                          |
|  9 browser tools + 1 VLM tool                                   |
|  DOMExtractor | Screenshot | ScreenshotAnalysis | FillInput |   |
|  SelectOption | Checkbox | ClickButton | DatePicker |           |
|  UploadFile | GetValidationErrors                                |
+------------------------------------------------------------------+
         |
         v
+------------------------------------------------------------------+
|                   Browser (Playwright Chromium)                   |
|  BrowserManager: sync API lifecycle (start/navigate/close)       |
+------------------------------------------------------------------+
```

---

## 2. Layer Details

### 2.1 CLI Layer (`src/main.py`)

Entry point using Click framework. Three commands:

| Command | Arguments | Description |
|---|---|---|
| `run` | `test_file --url --max-pages --max-retries` | Full form test execution |
| `validate` | `test_file --url` | Parse and validate without running |
| `analyze` | `url --visual/--no-visual` | Extract form fields from a page |

The CLI handles NL vs. structured file routing at the top level:
- `.txt` files: passes `test_input_path` to Flow (browser needed for parsing)
- Other files: parses upfront via `parse_test_file()`, then iterates over `TestCase` objects

### 2.2 Flow Layer (`src/flow/form_test_flow.py`)

CrewAI Flow state machine managing the full test lifecycle.

**State Model** (`FormTestState`):
```
FormTestState(BaseModel):
  test_input_path, target_url          # Input
  test_case_data, test_case_id         # Parsed test case
  page_context                         # DOM fields (for NL parsing)
  current_page_index, consumed_fields  # Page loop tracking
  page_results                         # Accumulated results per page
  verification_passed, retry_count     # Current page state
  validation_errors                    # Current page errors
  overall_status, screenshots          # Final output
  start_time                           # Timing
```

**Flow Event Chain (Standard Path)**:
```
@start parse_test_case
    |
    +--[@router]--> "open_browser"
                       |
                       +--[@listen]--> open_browser_and_navigate
                                          |
                                          +--> _run_page_loop()
                                                  |
                                                  +--> process_page() [loop]
                                                  |       |
                                                  |       +--> build_page_crew()
                                                  |       +--> crew.kickoff()
                                                  |       +--> _update_state_from_crew_result()
                                                  |
                                                  +--> [decide: next_page / retry / complete]
                                                  |
                                                  +--> generate_report()
```

**Flow Event Chain (NL Path)**:
```
@start parse_test_case
    |
    +--[@router]--> "pre_analyze"
                       |
                       +--[@listen]--> pre_analyze_page
                                          |
                                          +--> BrowserManager.start()
                                          +--> DOMExtractorTool._run()
                                          +--> parse_test_file(page_context=...)
                                          +--> _run_page_loop()  (same loop)
```

**Important architectural note**: `_run_page_loop()` is a manual while-loop that drives `process_page()` directly. It cannot use `@listen`/`@router` decorators because CrewAI Flow's event system only triggers when methods are invoked by the Flow scheduler, not by direct Python calls.

### 2.3 Crew Layer (`src/flow/page_crew.py`)

Builds a 4-agent sequential `Crew` for each page iteration.

```
build_page_crew(page, settings) -> Crew:
    +-- LLM(model, base_url, api_key)
    |
    +-- create_page_analyzer(page, llm, settings)  --> Agent + tools
    +-- create_field_mapper(llm)                    --> Agent (no tools)
    +-- create_form_filler(page, llm)               --> Agent + tools
    +-- create_result_verifier(page, llm, settings) --> Agent + tools
    |
    +-- Task chain: analyze -> map -> fill -> verify
    |   (each task receives context from previous tasks)
    |
    +-- Crew(process=Process.sequential, verbose=True)
```

The Crew receives these inputs at kickoff:
- `test_data`: JSON string of remaining test case fields
- `consumed_fields`: JSON list of field keys already filled in previous pages
- `validation_errors`: JSON list of errors from the previous attempt (for retry)

### 2.4 Tool Layer (`src/tools/`)

Ten tool classes, each wrapping Playwright browser actions:

| Tool | File | Description |
|---|---|---|
| DOM Extractor | `dom_extractor_tool.py` | JavaScript-based extraction of all form elements, buttons, errors |
| Screenshot | `screenshot_tool.py` | Captures page screenshot, saves to disk |
| Screenshot Analysis | `screenshot_analysis_tool.py` | VLM-powered visual analysis of screenshot |
| Fill Input | `fill_input_tool.py` | Fill text/email/phone inputs (self-healing: fill -> press_sequentially) |
| Select Option | `select_option_tool.py` | Select dropdown option by value or text |
| Checkbox Toggle | `checkbox_tool.py` | Toggle checkbox/radio (presses Escape after) |
| Click Button | `click_button_tool.py` | Click any button by selector |
| Date Picker | `date_picker_tool.py` | Fill date picker fields |
| Upload File | `upload_file_tool.py` | Upload file via file input |
| Get Validation Errors | `validation_error_tool.py` | Detect validation error messages from DOM |

**Agent-Tool assignment**:
- Page Analyzer: DOMExtractor, Screenshot, ScreenshotAnalysis (optional)
- Field Mapper: (none -- pure LLM reasoning)
- Form Filler: FillInput, SelectOption, Checkbox, ClickButton, DatePicker, UploadFile
- Result Verifier: Screenshot, GetValidationErrors

---

## 3. Data Flow

### 3.1 End-to-End Data Flow

```
Test File                         Browser
(.json/.yaml/.csv/.xlsx/.txt)     (Playwright Chromium)
    |                                 |
    v                                 |
+----------+                          |
| Parser   |  TestCase                |
| Factory  |---+                      |
+----------+   |                      |
               v                      |
         +------------+               |
         | FormTest   |  start()      |
         | Flow       |-------------->|
         | (state     |               |
         |  machine)  |               |
         +-----+------+               |
               |                      |
               | per page loop        |
               v                      |
         +------------+               |
         | Page Crew  |               |
         | (4 agents) |               |
         +-----+------+               |
               |                      |
               | tool invocations     |
               v                      v
         +------------+     +-------------------+
         | Tool Layer |<--->| Playwright Page    |
         | (9 tools)  |     | (shared instance)  |
         +-----+------+     +-------------------+
               |
               | per-page results
               v
         +------------+
         | Report     |  JSON + HTML
         | Generator  |-----------> reports/
         +------------+
```

### 3.2 Per-Page Data Flow (Inside Crew)

```
                      test_data (JSON)
                      consumed_fields
                      validation_errors
                            |
                            v
+------------------+   DOM fields JSON    +------------------+
| Page Analyzer    |--------------------->| Field Mapper     |
| (DOM + VLM +     |   screenshot path    | (pure LLM)      |
|  screenshot)     |                      |                  |
+------------------+                      +--------+---------+
                                                   |
                                          mappings JSON
                                          (field->value->selector)
                                                   |
                                                   v
                                          +------------------+
                                          | Form Filler      |
                                          | (6 browser tools)|
                                          +--------+---------+
                                                   |
                                          field_results JSON
                                                   |
                                                   v
                                          +------------------+
                                          | Result Verifier  |
                                          | (screenshot +    |
                                          |  error check)    |
                                          +--------+---------+
                                                   |
                                                   v
                                          verification JSON
                                          (passed, new_page_id,
                                           is_final_page, errors)
```

---

## 4. State Management

### 4.1 Flow State (`FormTestState`)

A Pydantic `BaseModel` that accumulates data across the entire test run:

- **Page tracking**: `current_page_index` increments per page, `consumed_fields` grows as fields are filled across pages
- **Retry logic**: `retry_count` resets to 0 on page advance, increments on verification failure (up to `max_retries`)
- **Page results**: `page_results: list[dict]` accumulates per-page results including field-level detail, timing, and token usage
- **Verification state**: `verification_passed`, `validation_errors`, and `current_page_id` are overwritten per page iteration

### 4.2 Crew Result Parsing

The Flow extracts structured data from the last Crew task (Result Verifier) output:
1. Attempts to parse the entire output as JSON
2. Falls back to extracting the last JSON object from the text (using brace-matching)
3. Falls back to heuristic keyword detection (`"error"`, `"fail"` in output)

Key fields extracted: `passed`, `new_page_id`, `is_final_page`, `validation_errors`, `consumed_keys`, `field_results`, `screenshot_path`

---

## 5. Browser Lifecycle

`BrowserManager` (`src/browser/browser_manager.py`) encapsulates the Playwright sync API:

```
BrowserManager(settings)
    |
    +-- start() -> Page
    |     sync_playwright().start()
    |     chromium.launch(headless=..., proxy=...)
    |     browser.new_context(viewport=...)
    |     context.set_default_timeout(...)
    |     context.new_page()
    |
    +-- navigate(url)
    |     page.goto(url, wait_until="networkidle")
    |
    +-- page (property)
    |     Returns the shared Page instance
    |
    +-- close()
          context.close()
          browser.close()
          playwright.stop()
```

- A single `Page` instance is shared across all agents and tools within a test run
- The browser is started once and closed after report generation (or on error)
- In the NL path, the browser is started during `pre_analyze_page()` and reused for the page loop
- Configurable: headless mode, proxy, viewport dimensions, timeouts (all via `.env` / `Settings`)

---

## 6. Configuration Architecture

All configuration flows through `src/config.py:Settings` (Pydantic BaseSettings):

```
.env file
    |
    v
+-------------------+
| Settings          |  (pydantic-settings, env_file=".env")
|  openai_api_key   |
|  openai_api_base  |
|  llm_model        |  default: "gpt-5.2"
|  vlm_model        |  default: "gpt-5.2"
|  vlm_max_tokens   |  default: 1000
|  browser_headless  |  default: False
|  browser_timeout   |  default: 10000
|  browser_proxy     |
|  awa_max_steps     |  default: 50 (max pages)
|  awa_max_healing   |  default: 3 (max retries)
|  awa_screenshot_dir|  default: "reports/screenshots"
|  log_level         |  default: "INFO"
+-------------------+
    |
    +---> get_settings() -> Settings (factory function)
```

Settings are injected into:
- `FormTestFlow` (at construction)
- `build_page_crew()` (passed through to agent factories)
- `BrowserManager` (browser config)
- `NL parser` (LLM config for NL extraction)

---

## 7. Error Handling Architecture

Three levels of error handling with different strategies:

| Level | Strategy | Example |
|---|---|---|
| **Tool Level** | Self-healing (try/fallback/fail strings) | `FillInputTool`: fill() -> press_sequentially() -> "FAILED: ..." |
| **Crew Level** | Agent decides next action based on tool status strings | Form Filler continues filling other fields if one fails |
| **Flow Level** | Retry logic + graceful degradation | Retry page up to `max_retries`, then report PARTIAL/FAIL status |

- Tools never raise exceptions to agents
- Agents never raise exceptions to the Flow (CrewAI handles agent errors)
- The Flow catches JSON parsing failures from crew output with heuristic fallback
- The CLI catches `ValueError` from parsers and reports to stderr
