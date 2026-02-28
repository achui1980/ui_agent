from __future__ import annotations

from crewai import Agent, LLM


def create_data_generator(llm: LLM) -> Agent:
    """Create the Data Generator agent for dynamic test data generation.

    This agent receives page analysis output (field list with types, labels,
    options, constraints) and generates realistic test data for each field.
    It relies on the LLM's general knowledge to infer domain-specific
    constraints (e.g. Medicare eligibility age, valid date formats).
    """
    return Agent(
        role="Test Data Generator",
        goal=(
            "Generate realistic, semantically appropriate test data for ALL form "
            "fields discovered on the current page. The generated data must be "
            "plausible for the domain (e.g. Medicare forms need age >= 65), "
            "match field type constraints (dropdowns must use provided options, "
            "dates must match expected formats), and maintain consistency with "
            "persona data from previous pages."
        ),
        backstory=(
            "You are an expert test data engineer with deep knowledge of "
            "insurance, healthcare, Medicare, financial services, and general "
            "web application domains. You understand form field semantics and "
            "can generate realistic test data that satisfies business rules "
            "and validation constraints. You infer the domain from page content "
            "(titles, labels, field names) and generate data accordingly. "
            "You always maintain persona consistency across multi-step forms — "
            "if a name was generated on a previous page, you reuse it."
        ),
        tools=[],  # Pure LLM reasoning, no tools needed
        llm=llm,
        verbose=True,
    )
