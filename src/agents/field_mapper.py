from __future__ import annotations

from crewai import Agent, LLM


def create_field_mapper(llm: LLM) -> Agent:
    return Agent(
        role="Field Mapper",
        goal=(
            "Map test case data fields to page form fields using semantic matching. "
            "Handle name differences, value format conversions, and field ordering "
            "for cascading dropdowns."
        ),
        backstory=(
            "You are an insurance business domain expert who understands the "
            "semantic relationships between test data field names and form labels. "
            "You handle date splitting, name normalization, and cascading dependencies."
        ),
        tools=[],  # Pure LLM reasoning, no tools needed
        llm=llm,
        verbose=True,
    )
