# Dependencies - UI Agent

**AI-DLC Stage**: Inception / Reverse Engineering
**Generated**: 2026-02-28
**Project**: UI Agent - AI-Powered Web Form Testing System

---

## 1. External Dependencies

### 1.1 Runtime Dependencies (from `pyproject.toml`)

| Package | Version Constraint | Purpose |
|---|---|---|
| `crewai[tools]` | >= 0.86.0 | Multi-agent orchestration framework. Provides Agent, Task, Crew, Flow, LLM, BaseTool. The `[tools]` extra includes additional tool infrastructure |
| `openai` | >= 1.0 | OpenAI API client for LLM and VLM calls (used indirectly through CrewAI's LLM wrapper, and directly for VLM in ScreenshotAnalysisTool) |
| `playwright` | >= 1.49.0 | Browser automation (Chromium). Sync API for page interaction. Requires `playwright install chromium` post-install |
| `pydantic` | >= 2.0 | Data modeling and validation. All models, tool input schemas, and flow state inherit from `BaseModel` |
| `pydantic-settings` | >= 2.0 | Configuration management. `Settings(BaseSettings)` reads `.env` files |
| `openpyxl` | >= 3.1.0 | Excel file parsing (.xlsx/.xls) for test data input |
| `pyyaml` | >= 6.0 | YAML file parsing for test data input |
| `python-dotenv` | >= 1.0 | `.env` file loading (used by pydantic-settings) |
| `loguru` | >= 0.7 | Structured logging throughout the application |
| `jinja2` | >= 3.1 | HTML report template rendering |
| `click` | >= 8.1 | CLI framework for `ui-agent` command |

### 1.2 Dev Dependencies (from `pyproject.toml [project.optional-dependencies.dev]`)

| Package | Version Constraint | Purpose |
|---|---|---|
| `pytest` | >= 8.0 | Test framework |
| `pytest-asyncio` | >= 0.23 | Async test support |
| `flask` | >= 3.0 | Test server for integration tests |

### 1.3 Stdlib Dependencies (no install required)

| Module | Used In | Purpose |
|---|---|---|
| `json` | Parsers, flow, reporting, tools | JSON parsing and serialization |
| `csv` | `csv_parser.py` | CSV test file parsing |
| `os` | Multiple modules | File paths, directory creation |
| `time` | `form_test_flow.py` | Timing and duration tracking |
| `re` | `nl_parser.py` | Regex for camelCase-to-spaces conversion |
| `sys` | `main.py` | `sys.exit()` on errors |
| `typing` | Multiple modules | `Any` type hint for Playwright Page |
| `unittest.mock` | Tests | Mocking Playwright Page objects |

---

## 2. Internal Module Dependencies

### 2.1 Dependency Map

```
src/main.py
  +-- src/config.py (get_settings, Settings)
  +-- src/utils/logging.py (setup_logging)
  +-- src/parsers/parser_factory.py (parse_test_file)
  +-- src/flow/form_test_flow.py (FormTestFlow)
  +-- src/browser/browser_manager.py (BrowserManager)  [validate, analyze]
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)  [validate, analyze]
  +-- src/tools/screenshot_tool.py (ScreenshotTool)  [analyze]
  +-- src/tools/screenshot_analysis_tool.py (ScreenshotAnalysisTool)  [analyze]

src/flow/form_test_flow.py
  +-- src/config.py (Settings, get_settings)
  +-- src/browser/browser_manager.py (BrowserManager)
  +-- src/flow/page_crew.py (build_page_crew)
  +-- src/models/ (TestCase, TestReport, PageResult, FieldActionResult)
  +-- src/parsers/parser_factory.py (parse_test_file)
  +-- src/reporting/json_report.py (save_json_report)
  +-- src/reporting/html_report.py (save_html_report)
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)  [NL path only]

src/flow/page_crew.py
  +-- src/config.py (Settings)
  +-- src/agents/page_analyzer.py (create_page_analyzer)
  +-- src/agents/field_mapper.py (create_field_mapper)
  +-- src/agents/form_filler.py (create_form_filler)
  +-- src/agents/result_verifier.py (create_result_verifier)

src/agents/page_analyzer.py
  +-- src/config.py (Settings)
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)
  +-- src/tools/screenshot_tool.py (ScreenshotTool)
  +-- src/tools/screenshot_analysis_tool.py (ScreenshotAnalysisTool)

src/agents/field_mapper.py
  (no local dependencies -- pure LLM agent, no tools)

src/agents/form_filler.py
  +-- src/tools/fill_input_tool.py (FillInputTool)
  +-- src/tools/select_option_tool.py (SelectOptionTool)
  +-- src/tools/checkbox_tool.py (CheckboxTool)
  +-- src/tools/click_button_tool.py (ClickButtonTool)
  +-- src/tools/date_picker_tool.py (DatePickerTool)
  +-- src/tools/upload_file_tool.py (UploadFileTool)

src/agents/result_verifier.py
  +-- src/config.py (Settings)
  +-- src/tools/screenshot_tool.py (ScreenshotTool)
  +-- src/tools/validation_error_tool.py (GetValidationErrorsTool)

src/tools/*
  (all tools depend on Playwright Page object, passed at construction)
  (all tools depend on crewai.tools.BaseTool, pydantic.BaseModel)

src/parsers/parser_factory.py
  +-- src/config.py (Settings)
  +-- src/models/test_case.py (TestCase)
  +-- src/parsers/json_parser.py (parse_json)
  +-- src/parsers/yaml_parser.py (parse_yaml)
  +-- src/parsers/csv_parser.py (parse_csv)
  +-- src/parsers/excel_parser.py (parse_excel)
  +-- src/parsers/nl_parser.py (parse_natural_language)

src/parsers/nl_parser.py
  +-- src/config.py (Settings)
  +-- src/models/test_case.py (TestCase)
  +-- crewai.LLM (for LLM.call() -- NL extraction)

src/reporting/json_report.py
  (no local dependencies -- uses json stdlib)

src/reporting/html_report.py
  (no local dependencies -- uses jinja2)
  (reads templates/report.html)

src/browser/browser_manager.py
  +-- src/config.py (Settings)

src/config.py
  (no local dependencies -- leaf module)
```

### 2.2 Dependency Graph (ASCII)

```
                          +----------+
                          | main.py  |
                          +----+-----+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
        +-----------+   +----------+   +----------------+
        | config.py |   | parsers/ |   | flow/          |
        +-----------+   +----+-----+   | form_test_flow |
              ^              |         +-------+--------+
              |              |                 |
              |         +----+----+    +-------+--------+
              |         |         |    |                |
              |         v         v    v                v
              |    +--------+ +------+------+    +-----------+
              |    | models/| | nl_parser   |    | flow/     |
              |    +--------+ | (uses LLM)  |    | page_crew |
              |         ^     +-------------+    +-----+-----+
              |         |                              |
              |         |          +-------------------+
              |         |          |         |         |
              |         |          v         v         v
              |         |   +----------+ +--------+ +----------+
              |         |   | agents/  | | agents/| | agents/  |
              |         |   | page_    | | field_ | | form_    |
              |         |   | analyzer | | mapper | | filler   |
              |         |   +----+-----+ +--------+ +----+-----+
              |         |        |                        |
              |         |        v                        v
              |         |   +----------+            +----------+
              |         +---| tools/   |            | tools/   |
              |             | DOM, SS, |            | Fill,    |
              |             | VLM      |            | Select,  |
              |             +----+-----+            | Click,   |
              |                  |                  | etc.     |
              |                  v                  +----+-----+
              |         +----------------+               |
              +---------| browser/       |<--------------+
                        | browser_manager|
                        +-------+--------+
                                |
                                v
                        +----------------+
                        | Playwright     |
                        | (Chromium)     |
                        +----------------+
```

---

## 3. Dependency Flow Summary

### 3.1 Import Direction Rules

- **Top-down**: `main.py` -> `flow` -> `crew` -> `agents` -> `tools`
- **Shared services**: `config.py` and `models/` are imported at every level
- **No circular dependencies**: Tools do not import agents, agents do not import flow
- **Parser isolation**: Parsers use relative imports within their package (`from .json_parser import parse_json`)
- **Browser isolation**: `BrowserManager` is only imported by `main.py` (for `validate`/`analyze`) and `form_test_flow.py`

### 3.2 Dependency Injection Pattern

The Playwright `Page` object is the primary shared dependency:
1. `BrowserManager.start()` creates the `Page`
2. `Page` is passed to `build_page_crew(page, settings)`
3. `build_page_crew` passes `page` to each agent factory
4. Agent factories pass `page` to each tool constructor
5. Tools store `page` as an attribute and use it in `_run()`

This means all tools operate on the same browser page instance within a test run.

---

## 4. Known Dependency Issues

### 4.1 `requirements.txt` vs `pyproject.toml`

Both files exist. `pyproject.toml` is the authoritative dependency specification:

| In `pyproject.toml` | In `requirements.txt` | Notes |
|---|---|---|
| `crewai[tools]>=0.86.0` | `crewai[tools]>=0.86.0` | Match |
| `openai>=1.0` | (missing) | `requirements.txt` is incomplete |
| `playwright>=1.49.0` | `playwright>=1.49.0` | Match |
| `pydantic>=2.0` | `pydantic>=2.0` | Match |
| `pydantic-settings>=2.0` | `pydantic-settings>=2.0` | Match |
| `openpyxl>=3.1.0` | `openpyxl>=3.1.0` | Match |
| `pyyaml>=6.0` | `pyyaml>=6.0` | Match |
| `python-dotenv>=1.0` | `python-dotenv>=1.0` | Match |
| `loguru>=0.7` | `loguru>=0.7` | Match |
| `jinja2>=3.1` | `jinja2>=3.1` | Match |
| `click>=8.1` | `click>=8.1` | Match |

`requirements.txt` is missing `openai>=1.0` and does not include dev dependencies. It appears to be a supplementary file, not the primary install mechanism.

### 4.2 CrewAI Transitive Dependencies

The `crewai[tools]` package brings in significant transitive dependencies including LangChain components. These are managed by pip's resolver and are not explicitly pinned.

### 4.3 Playwright Post-Install Step

Playwright requires a separate binary installation step after `pip install`:
```bash
playwright install chromium
```
This is not automated by `pip install` and must be run manually or in CI.

### 4.4 Conda vs pip

The project uses conda for environment isolation (`conda activate ui_agent`) but pip for package installation (`pip install -e ".[dev]"`). CI does not use conda -- it uses `setup-python` directly. This means the conda environment is a local development convenience, not a hard requirement.
