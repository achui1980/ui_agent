# AGENTS.md — UI Agent Codebase Guide

## Project Overview

AI-powered web form testing system built with **CrewAI** (multi-agent orchestration) and **Playwright** (browser automation). Four cooperating LLM agents analyze, map, fill, and verify multi-step web forms given structured test data. Python 3.11+.

## Python Environment

**IMPORTANT**: All Python commands (running scripts, installing dependencies, running tests, etc.) require activating the conda virtual environment first:

```bash
conda activate ui_agent
```

Always run `conda activate ui_agent` before any `python`, `pip`, `pytest`, or `ui-agent` command. If the environment does not exist yet, create it with `conda create -n ui_agent python=3.11 && conda activate ui_agent`.

## Build & Run Commands

```bash
# Activate the virtual environment first (REQUIRED before every command below)
conda activate ui_agent

# Install dependencies
pip install -e ".[dev]"
playwright install chromium

# Run the CLI
ui-agent run test_data/sample_test.json --url "https://example.com/form"
ui-agent validate test_data/sample_test.yaml
ui-agent analyze "https://example.com/form"

# Run all tests
pytest

# Run a single test file
pytest tests/test_parsers/test_parsers.py

# Run a single test class
pytest tests/test_tools/test_tools.py::TestFillInputTool

# Run a single test method
pytest tests/test_tools/test_tools.py::TestFillInputTool::test_fill_success

# Run tests with verbose output
pytest -v

# Syntax-check a single module (no runtime deps needed)
python3 -m py_compile src/tools/fill_input_tool.py
```

## Project Structure

```
src/
  main.py                  # CLI entry point (Click commands: run, validate, analyze)
  config.py                # Pydantic Settings (reads from .env)
  agents/                  # CrewAI Agent factory functions (4 agents)
    page_analyzer.py       # DOM extraction + screenshot
    field_mapper.py        # Semantic matching (pure LLM, no tools)
    form_filler.py         # Executes fill/select/click actions
    result_verifier.py     # Post-submit verification
  browser/
    browser_manager.py     # Playwright lifecycle (start/navigate/close)
  flow/
    form_test_flow.py      # CrewAI Flow — state machine for full test run
    page_crew.py           # Builds a 4-agent Crew per form page
  models/                  # Pydantic data models
    test_case.py           # TestCase
    page_result.py         # FieldActionResult, PageResult
    report.py              # TestReport
  parsers/                 # Test file parsers (JSON/YAML/CSV/Excel/NL)
    parser_factory.py      # Dispatch by file extension
  reporting/               # Report generators (JSON + HTML via Jinja2)
  tools/                   # CrewAI Tool wrappers around Playwright actions
  utils/
    logging.py             # Loguru setup
tests/                     # pytest test suite
templates/
  report.html              # Jinja2 HTML report template
test_data/                 # Sample test case files (JSON, YAML, CSV)
```

## Code Style Guidelines

### Imports

- Always start modules with `from __future__ import annotations` for PEP 604 style unions.
- Order: stdlib, third-party, then local (`src.*`). Blank line between groups.
- Use absolute imports from project root: `from src.models import TestCase`, not relative.
- Exception: parsers use relative imports within the same package (`from .json_parser import parse_json`).

### Formatting

- 4-space indentation, no tabs.
- Max line length ~88 chars (Black-compatible). Break long strings with parenthesized continuation.
- Trailing commas in multi-line collections and function signatures.
- Double quotes for strings throughout.

### Type Annotations

- All function signatures must have return type annotations: `def foo(x: str) -> str:`.
- Use `dict[str, str]`, `list[TestCase]` (lowercase generics, Python 3.11+).
- Use `X | None` for optional types (enabled by `__future__.annotations`).
- Pydantic models use `Field(default=...)` for all settings fields.
- Playwright `Page` typed as `Any` in tool classes (with `model_config = {"arbitrary_types_allowed": True}`).

### Naming Conventions

- **Files**: `snake_case.py` (e.g., `form_test_flow.py`, `dom_extractor_tool.py`).
- **Classes**: `PascalCase` (e.g., `FormTestFlow`, `FillInputTool`, `BrowserManager`).
- **Functions/methods**: `snake_case` (e.g., `parse_test_file`, `create_page_analyzer`).
- **Constants**: defined as Pydantic `Field` defaults, not module-level `UPPER_CASE`.
- **Private members**: prefix with `_` (e.g., `self._browser`, `self._settings`).
- **Agent factory functions**: `create_<role>(page, llm) -> Agent` pattern.
- **Tool classes**: `<Action>Tool` with matching `<Action>Input` schema class.

### CrewAI Tool Pattern

Every browser tool follows this structure:
```python
class FooInput(BaseModel):
    """Describe inputs."""
    selector: str = Field(..., description="CSS selector")

class FooTool(BaseTool):
    name: str = "Human Readable Name"
    description: str = "What this tool does."
    args_schema: type[BaseModel] = FooInput
    page: Any = None
    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str) -> str:
        try:
            # Primary strategy
            return "SUCCESS: ..."
        except Exception:
            try:
                # Self-healing fallback
                return "HEALED: ..."
            except Exception as e:
                return "FAILED: ..."
```

### Error Handling

- Tools return status strings: `"SUCCESS: ..."`, `"HEALED: ..."`, or `"FAILED: ..."` — never raise exceptions.
- Self-healing pattern: primary approach in outer try, fallback in inner try, final `FAILED` in inner except.
- Flow/parsers raise `ValueError` for invalid input (e.g., unsupported file format, missing data).
- Logging uses `loguru.logger` (`logger.info`, `logger.warning`, `logger.debug`).

### Testing Conventions

- Tests live under `tests/` mirroring `src/` structure (`test_parsers/`, `test_tools/`, `test_flow/`).
- Group tests in classes: `class TestFillInputTool:` with methods `test_<scenario>`.
- Use `pytest` fixtures: shared fixtures in `tests/conftest.py`, local fixtures in test files.
- Browser tools are tested with `unittest.mock.MagicMock` as the Playwright `Page` — no real browser needed.
- Use `tmp_path` (pytest built-in) for file-based tests, not `tempfile` directly.
- Assertions check for status keywords: `assert "SUCCESS" in result`.
- Docstrings on test modules, not individual test methods.

### Pydantic Models

- All data models inherit from `pydantic.BaseModel`.
- Settings use `pydantic_settings.BaseSettings` with `model_config = {"env_file": ".env"}`.
- Keep models minimal — plain fields with type annotations, default values where appropriate.
- Use `model_dump()` for serialization (not `.dict()`).

### Configuration

- All config via `.env` file, loaded by `pydantic-settings` into `src/config.py:Settings`.
- Access settings through `get_settings()` factory function.
- Key env vars: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `LLM_MODEL`, `BROWSER_HEADLESS`, `BROWSER_PROXY`.

### Known Issues

- `Settings.model_config` needs `"extra": "ignore"` — `.env` contains vars not defined in `Settings` (e.g., `PYTHONHTTPSVERIFY`, `SSL_CERT_FILE`) causing `ValidationError`.
- `PageResult.validation_errors` is typed `list[dict]` but flow stores `list[str]` — keep types consistent.
- Only the first test case is executed per run (`form_test_flow.py:75`).
