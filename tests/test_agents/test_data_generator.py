"""Tests for the Data Generator agent factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestCreateDataGenerator:
    def test_creates_agent(self):
        with patch("src.agents.data_generator.Agent") as MockAgent:
            MockAgent.return_value = MagicMock(
                role="Test Data Generator",
                tools=[],
                goal="...persona...",
                backstory="...domain...",
            )
            from src.agents.data_generator import create_data_generator

            llm = MagicMock()
            agent = create_data_generator(llm)
            MockAgent.assert_called_once()
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs["role"] == "Test Data Generator"
            assert call_kwargs["tools"] == []
            assert call_kwargs["llm"] is llm

    def test_agent_has_no_tools(self):
        with patch("src.agents.data_generator.Agent") as MockAgent:
            MockAgent.return_value = MagicMock()
            from src.agents.data_generator import create_data_generator

            create_data_generator(MagicMock())
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs["tools"] == []

    def test_goal_mentions_persona(self):
        with patch("src.agents.data_generator.Agent") as MockAgent:
            MockAgent.return_value = MagicMock()
            from src.agents.data_generator import create_data_generator

            create_data_generator(MagicMock())
            call_kwargs = MockAgent.call_args[1]
            assert "persona" in call_kwargs["goal"].lower()

    def test_backstory_mentions_domain_inference(self):
        with patch("src.agents.data_generator.Agent") as MockAgent:
            MockAgent.return_value = MagicMock()
            from src.agents.data_generator import create_data_generator

            create_data_generator(MagicMock())
            call_kwargs = MockAgent.call_args[1]
            assert "domain" in call_kwargs["backstory"].lower()
