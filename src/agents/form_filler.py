from __future__ import annotations

from typing import Any

from crewai import Agent, LLM
from playwright.sync_api import Page

from src.tools.fill_input_tool import FillInputTool
from src.tools.select_option_tool import SelectOptionTool
from src.tools.checkbox_tool import CheckboxTool
from src.tools.click_button_tool import ClickButtonTool
from src.tools.date_picker_tool import DatePickerTool
from src.tools.upload_file_tool import UploadFileTool


def create_form_filler(
    page: Page,
    llm: LLM,
    collector: Any = None,
) -> Agent:
    return Agent(
        role="Form Filler",
        goal=(
            "Execute form filling actions precisely according to the field mapping. "
            "Fill each field in the correct order, handle cascading dropdowns with "
            "appropriate waits, and click the submit/next button when done. "
            "After filling all fields, include a 'field_results' array in your JSON "
            "output summarizing each field action: "
            '[{"field_id": "...", "selector": "...", "value": "...", '
            '"status": "success/failed/healed", "error_message": ""}]'
        ),
        backstory=(
            "You are a browser automation expert who has mastered handling every "
            "type of form control: text inputs, selects, checkboxes, radios, "
            "date pickers, and file uploads. You execute actions carefully and "
            "continue filling other fields if one fails."
        ),
        tools=[
            FillInputTool(page=page, collector=collector),
            SelectOptionTool(page=page, collector=collector),
            CheckboxTool(page=page, collector=collector),
            ClickButtonTool(page=page),
            DatePickerTool(page=page, collector=collector),
            UploadFileTool(page=page),
        ],
        llm=llm,
        verbose=True,
    )
