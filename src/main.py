"""CLI entry point for the UI Form Testing Agent."""

from __future__ import annotations

import json
import os
import sys

import click
from loguru import logger

from src.config import get_settings
from src.utils.logging import setup_logging


@click.group()
def cli() -> None:
    """UI Agent - AI-powered form testing system."""
    setup_logging()


@cli.command()
@click.argument("test_file")
@click.option("--url", "-u", required=True, help="Target form URL")
@click.option("--max-pages", default=50, help="Max pages to process")
@click.option("--max-retries", default=3, help="Max retries per page")
def run(test_file: str, url: str, max_pages: int, max_retries: int) -> None:
    """Run a full form test using the test case file."""
    from src.flow.form_test_flow import FormTestFlow
    from src.parsers.parser_factory import parse_test_file

    settings = get_settings()
    ext = os.path.splitext(test_file)[1].lower()

    if ext == ".txt":
        # NL files are handled inside the flow (need browser for page context)
        logger.info(f"Starting NL test run: {test_file} -> {url}")
        flow = FormTestFlow(settings=settings)
        flow.state.test_input_path = test_file
        flow.state.target_url = url
        flow.state.max_pages = max_pages
        flow.state.max_retries = max_retries
        result = flow.kickoff()
        logger.info(f"Test run complete. Status: {result}")
        return

    # Parse all test cases upfront
    test_cases = parse_test_file(test_file, url, settings)
    if not test_cases:
        logger.error("No test cases found in input file")
        sys.exit(1)

    logger.info(
        f"Starting test run: {test_file} -> {url} ({len(test_cases)} test case(s))"
    )

    all_results = []
    for i, tc in enumerate(test_cases):
        logger.info(f"--- Running case {i + 1}/{len(test_cases)}: {tc.test_id} ---")
        flow = FormTestFlow(settings=settings)
        flow.state.test_input_path = test_file
        flow.state.target_url = url
        flow.state.max_pages = max_pages
        flow.state.max_retries = max_retries
        flow._load_test_case(tc)

        result = flow.kickoff()
        all_results.append(result)

    # Summary
    logger.info(f"All {len(all_results)} test case(s) complete:")
    for r in all_results:
        if isinstance(r, dict):
            logger.info(
                f"  {r.get('test_case_id', '?')}: {r.get('overall_status', '?')}"
            )


@cli.command()
@click.argument("test_file")
@click.option("--url", "-u", default="", help="Target URL (required for .txt files)")
def validate(test_file: str, url: str) -> None:
    """Parse and validate a test case file without running."""
    from src.parsers.parser_factory import parse_test_file

    settings = get_settings()
    ext = os.path.splitext(test_file)[1].lower()

    page_context = None
    bm = None

    if ext == ".txt":
        if not url:
            click.echo(
                "Error: --url is required for natural language (.txt) files",
                err=True,
            )
            sys.exit(1)

        # Start browser and extract page context for NL parsing
        from src.browser.browser_manager import BrowserManager
        from src.tools.dom_extractor_tool import DOMExtractorTool

        click.echo(f"Analyzing page: {url}")
        bm = BrowserManager(settings)
        page = bm.start()
        bm.navigate(url)

        extractor = DOMExtractorTool(page=page)
        result = extractor._run()
        page_context = json.loads(result)
        fields = page_context.get("fields", [])
        click.echo(f"Page analyzed: {len(fields)} fields found\n")

    try:
        test_cases = parse_test_file(
            test_file,
            url,
            settings,
            page_context,
        )
        click.echo(f"Parsed {len(test_cases)} test case(s):\n")
        for tc in test_cases:
            click.echo(f"  ID: {tc.test_id}")
            click.echo(f"  URL: {tc.url}")
            click.echo(f"  Fields: {len(tc.data)}")
            click.echo(f"  Expected: {tc.expected_outcome}")
            if tc.description:
                click.echo(f"  Description: {tc.description}")
            click.echo(f"  Data: {json.dumps(tc.data, indent=4, ensure_ascii=False)}")
            click.echo()
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        sys.exit(1)
    finally:
        if bm:
            bm.close()


@cli.command()
@click.argument("url")
@click.option("--max-pages", default=50, help="Max pages to process")
@click.option("--max-retries", default=3, help="Max retries per page")
def generate(url: str, max_pages: int, max_retries: int) -> None:
    """Auto-fill a form with dynamically generated test data (no test file needed).

    The system navigates to the URL, analyzes each form page, generates
    realistic test data based on the fields it discovers, and fills the form
    automatically.  Multi-step forms are supported with cross-page persona
    consistency.
    """
    from src.flow.form_test_flow import FormTestFlow

    settings = get_settings()
    logger.info(f"Starting dynamic generation run: {url}")

    flow = FormTestFlow(settings=settings)
    flow.state.target_url = url
    flow.state.max_pages = max_pages
    flow.state.max_retries = max_retries
    flow.state.generation_mode = "dynamic"

    result = flow.kickoff()
    if isinstance(result, dict):
        logger.info(
            f"Generate run complete. Status: {result.get('overall_status', '?')}"
        )
    else:
        logger.info(f"Generate run complete. Status: {result}")


@cli.command()
@click.argument("url")
@click.option("--visual/--no-visual", default=True, help="Enable VLM visual analysis")
def analyze(url: str, visual: bool) -> None:
    """Analyze a single page (extract form fields) without filling."""
    from src.browser.browser_manager import BrowserManager
    from src.tools.dom_extractor_tool import DOMExtractorTool
    from src.tools.screenshot_tool import ScreenshotTool
    from src.tools.screenshot_analysis_tool import ScreenshotAnalysisTool

    settings = get_settings()
    bm = BrowserManager(settings)
    page = bm.start()
    bm.navigate(url)

    try:
        extractor = DOMExtractorTool(page=page)
        result = extractor._run()
        parsed = json.loads(result)
        click.echo("=== DOM Extraction ===")
        click.echo(json.dumps(parsed, indent=2, ensure_ascii=False))

        screenshot = ScreenshotTool(
            page=page, screenshot_dir=settings.awa_screenshot_dir
        )
        ss_result = screenshot._run()
        click.echo(f"\n{ss_result}")

        if visual and settings.vlm_model:
            click.echo("\n=== Visual Analysis (VLM) ===")
            analyzer = ScreenshotAnalysisTool(
                page=page,
                vlm_model=settings.vlm_model,
                vlm_api_key=settings.openai_api_key.get_secret_value(),
                vlm_api_base=settings.openai_api_base,
                vlm_max_tokens=settings.vlm_max_tokens,
                screenshot_dir=settings.awa_screenshot_dir,
            )
            analysis = analyzer._run()
            click.echo(analysis)
    finally:
        bm.close()


if __name__ == "__main__":
    cli()
