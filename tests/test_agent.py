import os
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.agent import AgentConfigurationError, dispatch_investigation_tool, run_agent


def fake_account_context(account_id: str) -> dict[str, Any]:
    return {"account_id": account_id}


class AgentToolTests(unittest.TestCase):
    @patch.dict(
        "app.agent._TOOL_FUNCTIONS",
        {"get_account_context": fake_account_context},
    )
    def test_dispatches_only_valid_account_ids(self):
        result = dispatch_investigation_tool(
            "get_account_context", {"account_id": "ACC-1"}
        )

        self.assertEqual(result, {"account_id": "ACC-1"})

    def test_rejects_unapproved_tools(self):
        with self.assertRaises(ValueError):
            dispatch_investigation_tool(
                "run_arbitrary_cypher", {"account_id": "ACC-1"}
            )

    def test_rejects_unexpected_tool_arguments(self):
        with self.assertRaises(ValueError):
            dispatch_investigation_tool(
                "get_account_context",
                {"account_id": "ACC-1", "query": "MATCH (n) DETACH DELETE n"},
            )

    @patch.dict(os.environ, {}, clear=True)
    def test_requires_explicit_provider_configuration(self):
        with self.assertRaises(AgentConfigurationError):
            run_agent("ACC-1")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
    @patch(
        "app.agent.dispatch_investigation_tool",
        return_value={"network": {"account_ids": ["ACC-1"]}},
    )
    @patch("app.agent.Anthropic")
    def test_uses_tool_and_returns_final_answer(
        self, anthropic_class: Any, run_tool: Any
    ):
        tool_call = SimpleNamespace(
            type="tool_use",
            id="call-1",
            name="get_account_context",
            input={"account_id": "ACC-1"},
        )
        tool_response = SimpleNamespace(content=[tool_call])
        text_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="The account is connected to one account.")],
        )
        client = anthropic_class.return_value
        client.messages.create.side_effect = [tool_response, text_response]

        result = run_agent("ACC-1")

        self.assertEqual(result["response"], "The account is connected to one account.")
        self.assertEqual(result["tools_called"], ["get_account_context"])
        self.assertTrue(result["human_review_required"])
        run_tool.assert_called_once_with(
            "get_account_context", {"account_id": "ACC-1"}
        )
        self.assertEqual(client.messages.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
