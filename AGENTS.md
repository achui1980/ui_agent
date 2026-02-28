# AGENTS.md — UI Agent Codebase Guide

## Project Overview

AI-powered web form testing system built with **CrewAI** (multi-agent orchestration) and **Playwright** (browser automation). Four cooperating LLM agents analyze, map, fill, and verify multi-step web forms given structured test data. Python 3.11+.

## Python Environment

**IMPORTANT**: All Python commands require activating the conda environment first:

```bash
conda activate ui_agent
```

If the environment does not exist: `conda create -n ui_agent python=3.11 && conda activate ui_agent`.

## Build & Run Commands

```bash
conda activate ui_agent

# Install
pip install -e ".[dev]"
playwright install chromium

# CLI
ui-agent run test_data/sample_test.json --url "https://example.com/form"
ui-agent validate test_data/sample_test.yaml
ui-agent analyze "https://example.com/form"

# Tests — all unit tests (E2E excluded by default)
pytest
pytest -v                       # verbose

# Single test file / class / method
pytest tests/test_tools/test_tools.py
pytest tests/test_tools/test_tools.py::TestFillInputTool
pytest tests/test_tools/test_tools.py::TestFillInputTool::test_fill_success

# E2E tests (requires real LLM API key + Flask test server)
pytest -m e2e

# Syntax check without runtime deps
python3 -m py_compile src/tools/fill_input_tool.py
```

## Project Structure

```
src/
  main.py                  # CLI entry point (Click: run, validate, analyze)
  config.py                # Pydantic Settings — SecretStr for API key
  agents/                  # CrewAI Agent factories (4 agents)
  browser/browser_manager.py  # Playwright lifecycle
  flow/
    form_test_flow.py      # CrewAI Flow state machine with error recovery
    page_crew.py           # Builds 4-agent Crew per page + FieldResultCollector
  models/
    test_case.py           # TestCase
    page_result.py         # FieldActionResult, PageResult
    report.py              # TestReport (5 statuses: PASS/PASS_WITH_RETRIES/PARTIAL/FAIL/ERROR)
  parsers/                 # JSON/YAML/CSV/Excel/NL parsers
  reporting/               # JSON + HTML report generators (Jinja2)
  tools/                   # CrewAI Tool wrappers around Playwright
    field_result_collector.py  # Thread-safe field action result collector
  utils/logging.py         # Loguru setup with PII sanitization filter
tests/
  conftest.py              # Shared fixtures
  test_cli.py, test_config.py  # Top-level tests
  test_e2e/                # E2E tests (@pytest.mark.e2e)
  test_flow/, test_parsers/, test_reporting/, test_tools/
test_data/                 # Sample test files (JSON, YAML, CSV)
test_server/app.py         # Flask test server (port 5555, 3-step insurance form)
```

## Code Style Guidelines

### Imports
- Always start modules with `from __future__ import annotations`.
- Order: stdlib → third-party → local (`src.*`). Blank line between groups.
- Use absolute imports: `from src.models import TestCase`, not relative.
- Exception: parsers use relative imports within the package.

### Formatting
- 4-space indentation, no tabs. Max line ~88 chars (Black-compatible).
- Trailing commas in multi-line collections and function signatures.
- Double quotes for strings throughout.
- Break long strings with parenthesized continuation.

### Type Annotations
- All function signatures must have return type annotations.
- Use lowercase generics: `dict[str, str]`, `list[TestCase]`.
- Use `X | None` for optional types (enabled by `__future__.annotations`).
- Playwright `Page` typed as `Any` in tool classes (with `model_config = {"arbitrary_types_allowed": True}`).

### Naming Conventions
- **Files**: `snake_case.py` — **Classes**: `PascalCase` — **Functions**: `snake_case`.
- **Private members**: prefix `_` (e.g., `self._browser`).
- **Agent factories**: `create_<role>(page, llm, settings=None) -> Agent`.
- **Tool classes**: `<Action>Tool` with matching `<Action>Input` schema.

### CrewAI Tool Pattern

```python
class FooInput(BaseModel):
    selector: str = Field(..., description="CSS selector")

class FooTool(BaseTool):
    name: str = "Human Readable Name"
    description: str = "What this tool does."
    args_schema: type[BaseModel] = FooInput
    page: Any = None
    collector: Any = None  # FieldResultCollector for tracking results
    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str) -> str:
        try:
            # Primary strategy
            self._record_result(selector, value, "SUCCESS: ...")
            return "SUCCESS: ..."
        except Exception:
            try:
                # Self-healing fallback
                return "HEALED: ..."
            except Exception as e:
                return "FAILED: ..."
```

Tools dismiss popups by pressing `Escape` after actions. All action tools record results to `self.collector` (a `FieldResultCollector`) when set.

### Error Handling
- Tools return status strings: `"SUCCESS: ..."`, `"HEALED: ..."`, `"FAILED: ..."` — never raise.
- Flow has error recovery: `_run_page_loop()` catches exceptions, sets `overall_status="ERROR"`, saves partial results.
- Flow/parsers raise `ValueError` for invalid input.
- Logging: `loguru.logger` with PII sanitization on INFO+ (DEBUG unfiltered).

### Security
- `openai_api_key` is `SecretStr` in `config.py` — use `.get_secret_value()` to access.
- `ScreenshotAnalysisTool.vlm_api_key` has `Field(exclude=True, repr=False)`.
- PII filter in `utils/logging.py` redacts SSN, email, API keys, phone, credit card at INFO+ level.
- `.env` excluded via `.gitignore`. Reports/logs also gitignored.

### Testing Conventions
- Tests mirror `src/` structure. Group in classes: `class TestFoo:` with `test_<scenario>` methods.
- Browser tools tested with `unittest.mock.MagicMock` as Playwright `Page`.
- Use `tmp_path` for file tests. Assertions: `assert "SUCCESS" in result`.
- Docstrings on test modules, not individual methods.
- E2E tests marked `@pytest.mark.e2e`, excluded from default `pytest` runs.

### Pydantic Models
- Data models: `pydantic.BaseModel`. Settings: `pydantic_settings.BaseSettings`.
- Use `model_dump()` for serialization (not `.dict()`).
- `TestReport.overall_status`: `PASS` | `PASS_WITH_RETRIES` | `PARTIAL` | `FAIL` | `ERROR`.

### Configuration
- All config via `.env`, loaded by `pydantic-settings` into `src/config.py:Settings`.
- Access: `get_settings()` factory. Key vars: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `LLM_MODEL`, `VLM_MODEL`, `BROWSER_HEADLESS`, `BROWSER_PROXY` (must be empty string if unused).

### AI-DLC Framework
This project uses the AI-DLC development lifecycle. Rules in `.github/copilot-instructions.md` and `.aidlc-rule-details/`. Documentation in `aidlc-docs/` (all in Chinese). When making significant changes, update `aidlc-docs/audit.md` and `aidlc-docs/aidlc-state.md`.
