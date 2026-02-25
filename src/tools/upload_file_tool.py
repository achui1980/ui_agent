from __future__ import annotations

import os
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from playwright.sync_api import Page


class UploadFileInput(BaseModel):
    selector: str = Field(
        ..., description="CSS selector of the file input element"
    )
    file_path: str = Field(
        ..., description="Absolute or relative path to the file to upload"
    )


class UploadFileTool(BaseTool):
    name: str = "Upload File"
    description: str = (
        "Upload a file to a file input element on the page."
    )
    args_schema: type[BaseModel] = UploadFileInput
    page: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, selector: str, file_path: str) -> str:
        if not os.path.isfile(file_path):
            return f"FAILED: File not found: {file_path}"
        try:
            locator = self.page.locator(selector)
            locator.set_input_files(file_path)
            return f"SUCCESS: Uploaded '{file_path}' to '{selector}'"
        except Exception as e:
            return f"FAILED: Could not upload to '{selector}': {e}"
