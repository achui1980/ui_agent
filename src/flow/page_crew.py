from __future__ import annotations

from crewai import Crew, Task, Process, LLM
from playwright.sync_api import Page

from src.config import Settings
from src.agents.page_analyzer import create_page_analyzer
from src.agents.data_generator import create_data_generator
from src.agents.field_mapper import create_field_mapper
from src.agents.form_filler import create_form_filler
from src.agents.result_verifier import create_result_verifier
from src.tools.field_result_collector import FieldResultCollector


def build_page_crew(
    page: Page,
    settings: Settings,
    generation_mode: str = "static",
) -> tuple[Crew, FieldResultCollector]:
    """Build a Crew of agents to process a single form page.

    When generation_mode is "dynamic", a 5th Data Generator agent is inserted
    between Page Analyzer and Field Mapper.  In "static" mode (default), the
    original 4-agent crew is built — no behavioral change.

    Returns a tuple of (Crew, FieldResultCollector) so the caller can
    extract tool-level field results after crew execution.
    """
    collector = FieldResultCollector()

    llm = LLM(
        model=settings.llm_model,
        base_url=settings.openai_api_base or None,
        api_key=settings.openai_api_key.get_secret_value(),
    )

    # Agents
    page_analyzer = create_page_analyzer(page, llm, settings)
    field_mapper = create_field_mapper(llm)
    form_filler = create_form_filler(page, llm, collector=collector)
    result_verifier = create_result_verifier(page, llm, settings)

    # Tasks (sequential with context chaining)
    analyze_task = Task(
        description=(
            "Analyze the current page using BOTH DOM extraction and visual analysis:\n"
            "1. Use DOM Extractor to extract all form elements with selectors, types, labels\n"
            "2. Use Screenshot Analysis to visually identify the page layout, custom components\n"
            "   (react-select dropdowns, date pickers, autocomplete fields), and any elements\n"
            "   that DOM extraction might miss or misclassify\n"
            "3. Use Screenshot to save a copy of the page for the report\n"
            "4. Cross-reference DOM data with visual analysis to determine the true type of\n"
            "   each field (e.g. a text input that is actually a react-select dropdown,\n"
            "   or a text input that is actually a date picker with calendar popup)\n"
            "5. Identify page title and step indicator (e.g. 'Step 3 of 7')\n"
            "6. Identify the submit/next button selector\n"
            "7. Detect any existing validation error messages"
        ),
        expected_output=(
            "JSON with:\n"
            "- page_id: page identifier (from title or step indicator)\n"
            "- fields: [{field_id, label, type, selector, required, options, group,\n"
            "            visual_type (the actual UI component type from visual analysis,\n"
            "            e.g. 'react-select', 'date-picker', 'autocomplete')}]\n"
            "- nav_button: {label, selector}\n"
            "- existing_errors: [error messages]\n"
            "- screenshot_path: path to saved screenshot\n"
            "- visual_notes: any additional observations from visual analysis"
        ),
        agent=page_analyzer,
    )

    # --- Dynamic mode: insert Data Generator between Analyzer and Mapper ---
    agents = [page_analyzer]
    tasks = [analyze_task]

    if generation_mode == "dynamic":
        data_generator = create_data_generator(llm)

        generate_task = Task(
            description=(
                "Generate realistic test data for ALL form fields on this page.\n\n"
                "Page analysis result: use context from Page Analyzer.\n"
                "Existing persona data from previous pages: {generation_persona}\n\n"
                "Rules:\n"
                "1. For EACH form field, generate a plausible value that matches its "
                "type and constraints.\n"
                "2. For dropdown/select fields, you MUST choose from the provided options "
                "list — do NOT invent options.\n"
                "3. For date fields, match the format indicated by the field's placeholder "
                "or label (e.g. MM/DD/YYYY, YYYY-MM-DD). If no format hint exists, "
                "use MM/DD/YYYY.\n"
                "4. For phone numbers, use the format suggested by placeholder or mask. "
                "If none, use (XXX) XXX-XXXX.\n"
                "5. For email fields, generate a realistic email address.\n"
                "6. For zip/postal code fields, generate a code that is consistent with "
                "the state/city if already in the persona.\n"
                "7. Infer the domain from page content (title, labels, field names). "
                "For example, if you see 'Medicare' or 'Enrollment', generate data "
                "appropriate for a Medicare-eligible person (age >= 65).\n"
                "8. MAINTAIN CONSISTENCY with persona data — if a name, date of birth, "
                "or address was generated on a previous page, reuse the same values.\n"
                "9. For checkbox/radio fields, choose a reasonable option.\n"
                "10. For required fields, always generate a value. For optional fields, "
                "generate a value only if it adds realism."
            ),
            expected_output=(
                "JSON with exactly two keys:\n"
                "- generated_data: {field_name: value, ...} for every field on this page\n"
                "- persona: {field_name: value, ...} the COMPLETE accumulated persona "
                "(merge previous persona with new data from this page)"
            ),
            agent=data_generator,
            context=[analyze_task],
        )

        agents.append(data_generator)
        tasks.append(generate_task)

        # Map task receives generated data via context chain
        map_task = Task(
            description=(
                "Map the generated test data to page fields.\n"
                "Generated data and page analysis: use context from previous tasks.\n"
                "Already consumed fields: {consumed_fields}\n"
                "Previous validation errors: {validation_errors}\n\n"
                "Rules:\n"
                "1. Use the generated_data from the Data Generator output to create "
                "field mappings.\n"
                "2. Semantically match generated data keys to page field labels "
                "(e.g. first_name -> 'First Name')\n"
                "3. Skip fields in consumed_fields\n"
                "4. If there are validation errors, adjust values/formats for those "
                "fields\n"
                "5. Handle value conversions (e.g. date split into month/day/year)\n"
                "6. Order by execution_order: parent cascading dropdowns before children"
            ),
            expected_output=(
                "JSON with:\n"
                "- mappings: [{field_id, selector, value, action_type, "
                "execution_order, wait_after_ms}]\n"
                "- unmapped_fields: [field labels without matching test data]\n"
                "- consumed_keys: [test data keys used in this page]"
            ),
            agent=field_mapper,
            context=[analyze_task, generate_task],
        )
    else:
        # Static mode: original map task with pre-supplied test data
        map_task = Task(
            description=(
                "Map test case data to page fields.\n"
                "Test data: {test_data}\n"
                "Already consumed fields: {consumed_fields}\n"
                "Previous validation errors: {validation_errors}\n\n"
                "Rules:\n"
                "1. Semantically match test data keys to page field labels "
                "(e.g. first_name -> 'First Name')\n"
                "2. Skip fields in consumed_fields\n"
                "3. If there are validation errors, adjust values/formats for "
                "those fields\n"
                "4. Handle value conversions (e.g. date split into month/day/year)\n"
                "5. Order by execution_order: parent cascading dropdowns before "
                "children"
            ),
            expected_output=(
                "JSON with:\n"
                "- mappings: [{field_id, selector, value, action_type, "
                "execution_order, wait_after_ms}]\n"
                "- unmapped_fields: [field labels without matching test data]\n"
                "- consumed_keys: [test data keys used in this page]"
            ),
            agent=field_mapper,
            context=[analyze_task],
        )

    agents.append(field_mapper)
    tasks.append(map_task)

    fill_task = Task(
        description=(
            "Fill the form fields according to the mapping:\n"
            "1. Process fields in execution_order\n"
            "2. text_input -> Fill Input tool\n"
            "3. select -> Select Option tool\n"
            "4. checkbox/radio -> Checkbox Toggle tool\n"
            "5. date_picker -> Date Picker tool\n"
            "6. file_upload -> Upload File tool\n"
            "7. For cascading dropdowns: wait after filling parent before filling child\n"
            "8. After all fields: Click Button on the submit/next button\n"
            "9. If a field fails, record the error but continue with remaining fields"
        ),
        expected_output=(
            "JSON with:\n"
            "- field_results: an array of objects for EVERY field action you performed, "
            "each with {field_id, selector, value, status, error_message}. "
            'status must be one of: "success", "failed", "healed". '
            "This array is REQUIRED even if all fields succeeded.\n"
            "- submit_clicked: true/false\n"
            "- submit_error: error message if submit failed"
        ),
        agent=form_filler,
        context=[map_task],
    )

    verify_task = Task(
        description=(
            "Verify the submission result:\n"
            "1. Use Screenshot to capture the post-submission page\n"
            "2. Use Get Validation Errors to detect form errors\n"
            "3. Check if the page transitioned (new title, URL, or step indicator)\n"
            "4. If this is the final page, look for confirmation number or success message\n"
            "5. For each validation error, identify the associated field and suggest a fix"
        ),
        expected_output=(
            "JSON with:\n"
            "- passed: true/false\n"
            "- page_transitioned: true/false\n"
            "- new_page_id: identifier of the new page\n"
            "- is_final_page: true/false (completion/confirmation page)\n"
            "- validation_errors: [{field, message, suggested_fix}]\n"
            "- screenshot_path: path to post-submission screenshot"
        ),
        agent=result_verifier,
        context=[analyze_task, fill_task],
    )

    agents.extend([form_filler, result_verifier])
    tasks.extend([fill_task, verify_task])

    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    ), collector
