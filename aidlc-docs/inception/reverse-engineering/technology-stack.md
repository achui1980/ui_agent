# Technology Stack - UI Agent

**AI-DLC Stage**: Inception / Reverse Engineering
**Generated**: 2026-02-28
**Project**: UI Agent - AI-Powered Web Form Testing System

---

## 1. Runtime

| Component | Version | Notes |
|---|---|---|
| **Python** | 3.11+ | Required (`requires-python = ">=3.11"`). Uses lowercase generics (`list[str]`, `dict[str, str]`), PEP 604 unions via `from __future__ import annotations` |
| **Conda** | (any) | Virtual environment management. Environment name: `ui_agent` |

---

## 2. AI / Agent Framework

| Component | Version | Role |
|---|---|---|
| **CrewAI** | >= 0.86.0 (`crewai[tools]`) | Multi-agent orchestration. Provides `Agent`, `Task`, `Crew`, `Process`, `Flow`, `LLM`, `BaseTool`. The `[tools]` extra includes built-in tool dependencies |
| **OpenAI API** | >= 1.0 (`openai`) | LLM provider (text + vision). Accessed through CrewAI's `LLM` wrapper. Configurable model, base URL, and API key via `.env` |

### AI Models Used

| Setting | Default | Purpose |
|---|---|---|
| `LLM_MODEL` | `gpt-5.2` | Primary LLM for all 4 agents + NL parser |
| `VLM_MODEL` | `gpt-5.2` | Vision Language Model for screenshot analysis |
| `VLM_MAX_TOKENS` | 1000 | Max tokens for VLM responses |
| `LLM_MAX_TOKENS` | 4096 | Max tokens for LLM responses |

The system supports any OpenAI-compatible API by configuring `OPENAI_API_BASE`.

---

## 3. Browser Automation

| Component | Version | Role |
|---|---|---|
| **Playwright** | >= 1.49.0 (`playwright`) | Browser automation. Sync API only (not async). Chromium browser |

### Playwright Usage

- **Sync API**: `sync_playwright().start()`, `chromium.launch()`, `page.goto()`, `page.locator()`, `page.evaluate()`
- **Browser**: Chromium only (installed via `playwright install chromium`)
- **Shared Page**: Single `Page` instance shared across all tools in a test run
- **JavaScript evaluation**: `DOMExtractorTool` uses `page.evaluate()` with inline JS to extract form elements
- **Configurable**: headless mode, proxy, viewport dimensions, default timeout, navigation timeout

---

## 4. Data Modeling

| Component | Version | Role |
|---|---|---|
| **Pydantic** | >= 2.0 (`pydantic`) | Data models (`TestCase`, `PageResult`, `FieldActionResult`, `TestReport`, `FormTestState`). Tool input schemas (`FillInputInput`, etc.) |
| **pydantic-settings** | >= 2.0 (`pydantic-settings`) | Configuration management. `Settings(BaseSettings)` reads from `.env` file with `model_config = {"env_file": ".env", "extra": "ignore"}` |

### Key Models

| Model | Location | Purpose |
|---|---|---|
| `TestCase` | `src/models/test_case.py` | Parsed test input: `test_id`, `url`, `data: dict[str, str]`, `expected_outcome` |
| `FieldActionResult` | `src/models/page_result.py` | Per-field result: `field_id`, `selector`, `value`, `status`, `error_message` |
| `PageResult` | `src/models/page_result.py` | Per-page result: fields filled, verification status, timing, token usage |
| `TestReport` | `src/models/report.py` | Full test report: pages, overall status, duration, token totals |
| `FormTestState` | `src/flow/form_test_flow.py` | Flow state machine: accumulated page results, consumed fields, retry state |
| `Settings` | `src/config.py` | All configuration (LLM, browser, logging) |

---

## 5. CLI

| Component | Version | Role |
|---|---|---|
| **Click** | >= 8.1 (`click`) | Command-line interface framework. `@click.group()` with 3 subcommands: `run`, `validate`, `analyze` |

Registered as console script: `ui-agent = "src.main:cli"` in `pyproject.toml`.

---

## 6. Parsers

| Component | Version | Role |
|---|---|---|
| **json** | stdlib | JSON test file parsing |
| **PyYAML** | >= 6.0 (`pyyaml`) | YAML test file parsing |
| **openpyxl** | >= 3.1.0 (`openpyxl`) | Excel (.xlsx/.xls) test file parsing |
| **csv** | stdlib | CSV test file parsing |
| **CrewAI LLM** | (via crewai) | Natural language (.txt) parsing -- uses `LLM.call()` for structured extraction |

Parser dispatch is handled by `parser_factory.py` which routes by file extension:
- `.json` -> `json_parser.parse_json()`
- `.yaml`/`.yml` -> `yaml_parser.parse_yaml()`
- `.csv` -> `csv_parser.parse_csv()`
- `.xlsx`/`.xls` -> `excel_parser.parse_excel()`
- `.txt` -> `nl_parser.parse_natural_language()` (requires `page_context` and `settings`)

---

## 7. Reporting

| Component | Version | Role |
|---|---|---|
| **Jinja2** | >= 3.1 (`jinja2`) | HTML report rendering from `templates/report.html` |
| **json** | stdlib | JSON report serialization |

Reports are saved to `reports/` directory:
- `reports/{test_case_id}_report.json` -- machine-readable
- `reports/{test_case_id}_report.html` -- human-readable (Jinja2 template)

---

## 8. Logging

| Component | Version | Role |
|---|---|---|
| **Loguru** | >= 0.7 (`loguru`) | Structured logging throughout the application. Setup in `src/utils/logging.py`. Used via `from loguru import logger` |

Configured via `LOG_LEVEL` environment variable (default: `INFO`).

---

## 9. Environment & Configuration

| Component | Version | Role |
|---|---|---|
| **python-dotenv** | >= 1.0 (`python-dotenv`) | `.env` file loading (used by pydantic-settings) |

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | (required) | API key for LLM/VLM provider |
| `OPENAI_API_BASE` | `""` | Custom API base URL (for OpenAI-compatible providers) |
| `HTTPS_PROXY` | `""` | HTTP proxy for API calls |
| `LLM_MODEL` | `gpt-5.2` | Primary LLM model name |
| `VLM_MODEL` | `gpt-5.2` | Vision model name |
| `BROWSER_HEADLESS` | `False` | Run browser in headless mode |
| `BROWSER_PROXY` | `""` | Browser proxy server |
| `BROWSER_VIEWPORT_WIDTH` | `1280` | Browser viewport width |
| `BROWSER_VIEWPORT_HEIGHT` | `720` | Browser viewport height |
| `BROWSER_TIMEOUT` | `10000` | Default action timeout (ms) |
| `BROWSER_NAVIGATION_TIMEOUT` | `60000` | Navigation timeout (ms) |
| `AWA_MAX_STEPS` | `50` | Maximum pages to process |
| `AWA_MAX_HEALING_ATTEMPTS` | `3` | Maximum retries per page |
| `AWA_SCREENSHOT_DIR` | `reports/screenshots` | Screenshot output directory |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## 10. Testing

| Component | Version | Role |
|---|---|---|
| **pytest** | >= 8.0 (`pytest`) | Test framework. Tests under `tests/` mirroring `src/` structure |
| **pytest-asyncio** | >= 0.23 (`pytest-asyncio`) | Async test support (dev dependency) |
| **unittest.mock** | stdlib | Mocking Playwright `Page` for tool unit tests |
| **Flask** | >= 3.0 (`flask`) | Dev dependency (likely for test server fixtures) |

### Test Conventions
- Tests grouped in classes: `class TestFillInputTool`
- Browser tools tested with `MagicMock` page objects -- no real browser needed
- Shared fixtures in `tests/conftest.py`
- Status keyword assertions: `assert "SUCCESS" in result`

---

## 11. CI/CD

| Component | Configuration | Notes |
|---|---|---|
| **GitHub Actions** | `.github/workflows/ci.yml` | Runs on push/PR to `main` |
| **Python Matrix** | 3.11, 3.12 | Tests against both versions |
| **Test Command** | `pytest -v --tb=short` | Verbose with short tracebacks |

CI pipeline:
1. Checkout code
2. Set up Python (matrix: 3.11, 3.12)
3. Install dependencies (`pip install -e ".[dev]"`)
4. Run tests with dummy `OPENAI_API_KEY`

---

## 12. Package Management

| Component | Role |
|---|---|
| **pip** | Package installer |
| **setuptools** | Build backend (`setuptools >= 68.0`, `wheel`) |
| **pyproject.toml** | Primary dependency specification (PEP 621) |
| **requirements.txt** | Supplementary (subset of pyproject.toml deps, missing `openai`) |
| **conda** | Environment management (not for dependency resolution) |

Install: `pip install -e ".[dev]"` (editable install with dev dependencies)
