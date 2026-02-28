# UI Agent

AI-powered web form testing system built with [CrewAI](https://github.com/crewAIInc/crewAI) (multi-agent orchestration) and [Playwright](https://playwright.dev/python/) (browser automation).

Four cooperating LLM agents analyze, map, fill, and verify multi-step web forms given structured test data.

## Quick Start

```bash
# Create and activate conda environment
conda create -n ui_agent python=3.11
conda activate ui_agent

# Install dependencies
pip install -e ".[dev]"
playwright install chromium

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API key and settings

# Run a form test
ui-agent run test_data/sample_test.json --url "https://example.com/form"

# Validate a test file without running
ui-agent validate test_data/sample_test.yaml --url "https://example.com/form"

# Analyze a page's form fields
ui-agent analyze "https://example.com/form"
```

## Architecture

```
                    CLI (Click)
                        |
                  FormTestFlow (CrewAI Flow)
                        |
              +---------+---------+
              |                   |
         NL Path             Standard Path
     (browser + LLM          (JSON/YAML/
      pre-analysis)           CSV/Excel)
              |                   |
              +------- + --------+
                       |
                 Page Crew (per page)
                       |
         +------+------+------+------+
         |      |      |      |      |
      Analyze  Map   Fill   Verify
      (DOM +  (LLM) (Play- (Play-
       VLM)         wright) wright)
```

**Agents:**
- **Page Analyzer** - Extracts DOM fields + VLM visual analysis
- **Field Mapper** - Semantically matches test data to form fields
- **Form Filler** - Executes fill/select/click actions via Playwright
- **Result Verifier** - Validates submission results

## Test Data Formats

| Format | Extension | Example |
|--------|-----------|---------|
| JSON | `.json` | `test_data/sample_test.json` |
| YAML | `.yaml` | `test_data/sample_test.yaml` |
| CSV | `.csv` | `test_data/sample_test.csv` |
| Excel | `.xlsx` | `test_data/sample_test.xlsx` |
| Natural Language | `.txt` | `test_data/sample_nl.txt` (requires `--url`) |

## Configuration

All configuration via `.env` file. See `.env.example` for all available options.

Key settings:
- `OPENAI_API_KEY` - Your OpenAI API key
- `LLM_MODEL` / `VLM_MODEL` - Model names for text and vision tasks
- `BROWSER_HEADLESS` - Run browser in headless mode (default: false)
- `AWA_MAX_STEPS` - Maximum pages to process per test (default: 50)

## Development

```bash
conda activate ui_agent

# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_tools/test_tools.py

# Syntax-check a module
python3 -m py_compile src/tools/fill_input_tool.py
```

## Project Structure

```
src/
  main.py                  # CLI entry point
  config.py                # Settings (pydantic-settings)
  agents/                  # CrewAI Agent factories (4 agents)
  browser/                 # Playwright lifecycle management
  flow/                    # CrewAI Flow orchestration
  models/                  # Pydantic data models
  parsers/                 # Test file parsers (JSON/YAML/CSV/Excel/NL)
  reporting/               # Report generators (JSON + HTML)
  tools/                   # CrewAI Tool wrappers (9 browser tools)
  utils/                   # Logging setup
tests/                     # pytest test suite
templates/                 # Jinja2 HTML report template
test_data/                 # Sample test case files
test_server/               # Flask test server (3-step insurance form)
```

## Reports

After each test run, reports are saved to `reports/`:
- `{test_id}_report.json` - Machine-readable JSON report
- `{test_id}_report.html` - Human-readable HTML report with timing and token usage
- `screenshots/` - Page screenshots captured during testing
