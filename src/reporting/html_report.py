from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader
from loguru import logger


def save_html_report(report: dict, test_case_id: str) -> str:
    """Render and save test report as HTML using Jinja2 template."""
    os.makedirs("reports", exist_ok=True)

    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "templates"
    )
    template_dir = os.path.abspath(template_dir)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
    )
    template = env.get_template("report.html")
    html = template.render(report=report)

    path = f"reports/{test_case_id}_report.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML report saved: {path}")
    return path
