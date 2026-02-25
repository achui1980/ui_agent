"""CLI entry point for the UI Form Testing Agent."""

from __future__ import annotations

import json
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

    settings = get_settings()
    flow = FormTestFlow(settings=settings)
    flow.state.test_input_path = test_file
    flow.state.target_url = url
    flow.state.max_pages = max_pages
    flow.state.max_retries = max_retries

    logger.info(f"Starting test run: {test_file} -> {url}")
    result = flow.kickoff()
    logger.info(f"Test run complete. Status: {result}")


@cli.command()
@click.argument("test_file")
@click.option("--url", "-u", default="", help="Default URL if not in file")
def validate(test_file: str, url: str) -> None:
    """Parse and validate a test case file without running."""
    from src.parsers.parser_factory import parse_test_file

    settings = get_settings()
    try:
        test_cases = parse_test_file(test_file, url, settings)
        click.echo(f"Parsed {len(test_cases)} test case(s):\n")
        for tc in test_cases:
            click.echo(f"  ID: {tc.test_id}")
            click.echo(f"  URL: {tc.url}")
            click.echo(f"  Fields: {len(tc.data)}")
            click.echo(f"  Expected: {tc.expected_outcome}")
            if tc.description:
                click.echo(f"  Description: {tc.description}")
            click.echo(f"  Data: {json.dumps(tc.data, indent=4)}")
            click.echo()
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        sys.exit(1)


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

        screenshot = ScreenshotTool(page=page)
        ss_result = screenshot._run()
        click.echo(f"\n{ss_result}")

        if visual and settings.vlm_model:
            click.echo("\n=== Visual Analysis (VLM) ===")
            analyzer = ScreenshotAnalysisTool(
                page=page,
                vlm_model=settings.vlm_model,
                vlm_api_key=settings.openai_api_key,
                vlm_api_base=settings.openai_api_base,
                vlm_max_tokens=settings.vlm_max_tokens,
            )
            analysis = analyzer._run()
            click.echo(analysis)
    finally:
        bm.close()


if __name__ == "__main__":
    cli()
