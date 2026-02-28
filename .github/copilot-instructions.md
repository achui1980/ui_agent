# UI Agent — AI Instructions

AI-powered web form testing system using **CrewAI** (multi-agent orchestration) + **Playwright** (browser automation). Four cooperating LLM agents analyze, map, fill, and verify multi-step web forms using structured test data.

## Python Environment (CRITICAL)

**ALWAYS activate the conda environment first:**
```bash
conda activate ui_agent
```
Required before ANY Python command: `pip`, `pytest`, `ui-agent`, `python`. If the environment doesn't exist: `conda create -n ui_agent python=3.11 && conda activate ui_agent`

## Quick Start

```bash
# Install (after activating environment)
pip install -e ".[dev]"
playwright install chromium

# Run tests
ui-agent run test_data/sample_test.json --url "https://example.com/form"
ui-agent validate test_data/demoqa_nl_test.txt --url "https://demoqa.com/form"
ui-agent analyze "https://example.com/form"

# Test suite
pytest                                    # All tests
pytest tests/test_tools/test_tools.py     # Single file
pytest tests/test_tools/test_tools.py::TestFillInputTool::test_fill_success  # Single test
```

## Architecture (Multi-Agent System)

**CrewAI Flow** = state machine orchestrating 4 specialized agents per form page:

1. **Page Analyzer** (`src/agents/page_analyzer.py`) — DOM extraction + VLM screenshot analysis → identifies all available fields
2. **Field Mapper** (`src/agents/field_mapper.py`) — Semantic matching (pure LLM, no tools) → maps test data keys to actual form fields
3. **Form Filler** (`src/agents/form_filler.py`) — Executes Playwright actions (fill, select, click) → completes form fields
4. **Result Verifier** (`src/agents/result_verifier.py`) — Post-submit verification → confirms success/failure

**Flow Entry Point**: `src/flow/form_test_flow.py` (CrewAI Flow with `@start`, `@listen`, `@router` decorators)
- Handles multi-step forms (next page detection)
- Manages state across pages (`FormTestState`)
- Drives agent cooperation via `src/flow/page_crew.py`

## Code Patterns

### Tool Structure (Self-Healing Pattern)
Every browser tool in `src/tools/` follows this template:
```python
class FooInput(BaseModel):
    selector: str = Field(..., description="CSS selector")
    value: str

class FooTool(BaseTool):
    name: str = "Human Readable Name"
    description: str = "What this tool does"
    args_schema: type[BaseModel] = FooInput
    page: Any = None  # Playwright Page
    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, value: str) -> str:
        try:
            # Primary strategy (e.g., .fill())
            return "SUCCESS: ..."
        except Exception:
            try:
                # Self-healing fallback (e.g., .press_sequentially())
                return "HEALED: ..."
            except Exception as e:
                return "FAILED: ..."  # Never raise
```
**Critical**: Tools return status strings (`SUCCESS`/`HEALED`/`FAILED`) — never raise exceptions. Popup dismissal via `.press("Escape")` after fill/checkbox actions prevents blocking overlays.

### Natural Language Test Parsing (Two-Stage)
`.txt` files require special handling:
1. **Stage 1** (`pre_analyze_page()`) — Open browser → extract DOM fields → build `page_context`
2. **Stage 2** (`src/parsers/nl_parser.py`) — LLM maps NL description to actual form fields using `page_context`

**Flow routing**: `@router(parse_test_case)` returns `"pre_analyze"` for `.txt` files, triggering DOM extraction before parsing. Direct method calls bypass Flow events, so NL path uses manual loop (`_run_page_loop()`).

### Type Annotations & Imports
- **Always** start with `from __future__ import annotations` (enables `X | None` syntax)
- Use lowercase generics: `dict[str, str]`, `list[TestCase]` (Python 3.11+)
- Absolute imports: `from src.models import TestCase` (not relative, except within `src/parsers/`)
- Function returns always typed: `def foo(x: str) -> str:`
- Playwright `Page` typed as `Any` in tools (with `arbitrary_types_allowed`)

### Testing with Mocks
Browser tools tested with `unittest.mock.MagicMock` — no real browser needed:
```python
@pytest.fixture
def mock_page():
    page = MagicMock()
    page.locator.return_value = MagicMock()  # Mock the locator chain
    return page

def test_fill(mock_page):
    tool = FillInputTool(page=mock_page)
    result = tool._run("#name", "John")
    assert "SUCCESS" in result
```
Check `tests/test_tools/test_tools.py` for examples. Use `tmp_path` (pytest built-in) for file-based tests.

## Configuration

All config via `.env` → loaded by `src/config.py:Settings` (Pydantic):
```bash
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1  # Optional proxy
LLM_MODEL=gpt-5.2
VLM_MODEL=gpt-5.2  # Vision model for screenshots
BROWSER_HEADLESS=false  # Set true for CI
BROWSER_PROXY=http://proxy:8080  # Optional
```
Access via `get_settings()` factory function (not direct instantiation).

## File Naming & Style

- **Files**: `snake_case.py` (e.g., `form_test_flow.py`, `dom_extractor_tool.py`)
- **Classes**: `PascalCase` (e.g., `FormTestFlow`, `FillInputTool`, `BrowserManager`)
- **Functions**: `snake_case` (e.g., `parse_test_file`, `create_page_analyzer`)
- **Agent factory**: `create_<role>(page, llm, settings=None) -> Agent` pattern
- **Tool classes**: `<Action>Tool` + `<Action>Input` schema class
- **Formatting**: 4-space indent, ~88 char lines (Black-compatible), double quotes, trailing commas

## Known Issues & Quirks

- **Only first test case executes** per run (`form_test_flow.py:75` — loop needed)
- **Type mismatch**: `PageResult.validation_errors` defined as `list[dict]` but flow stores `list[str]` — align types when fixing
- **CrewAI Flow caveat**: Direct method calls (`self.foo()`) bypass `@listen`/`@router` event system — only Flow scheduler triggers listeners
- **Natural language parsing requires URL**: `--url` mandatory for `.txt` files (both `run` + `validate` commands) to extract page context

## Project Structure Quick Reference

```
src/
  main.py                  # CLI entry (Click commands: run/validate/analyze)
  config.py                # Pydantic Settings (.env loader)
  agents/                  # 4 CrewAI agents (analyzer/mapper/filler/verifier)
  browser/browser_manager.py  # Playwright lifecycle wrapper
  flow/
    form_test_flow.py      # CrewAI Flow state machine (main orchestrator)
    page_crew.py           # Builds 4-agent Crew per page
  models/                  # Pydantic data models (TestCase, PageResult, TestReport)
  parsers/                 # Test file parsers (JSON/YAML/CSV/Excel/NL)
  tools/                   # CrewAI Tools wrapping Playwright actions
  reporting/               # JSON + HTML report generators (Jinja2 templates)
tests/                     # pytest suite (mirrors src/ structure)
templates/report.html      # HTML report template
test_data/                 # Sample test cases (JSON/YAML/CSV/TXT)
```

**Key insight**: Understanding CrewAI Flow's event-driven model (`@start`/`@listen`/`@router`) is essential — it's not a linear function chain. Read `src/flow/form_test_flow.py` first when debugging flow logic.

See `AGENTS.md` for deeper implementation details and coding patterns.
