"""Anthropic tool-calling agent with a fixed, read-only investigation toolset."""

import json
import os
import re
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolParam, ToolResultBlockParam

from app.graph_service import (
    get_account_context,
    investigate_account,
    trace_fund_flows,
)

MAX_AGENT_TURNS = 5
MAX_TOOL_CALLS = 8
ACCOUNT_ID_PATTERN = re.compile(r"^ACC-[A-Za-z0-9_-]{1,60}$")

TOOLS: list[ToolParam] = [
    {
        "name": "get_account_context",
        "description": (
            "Get the owner and connected customer/account network for an account."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "pattern": "^ACC-[A-Za-z0-9_-]{1,60}$",
                }
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "trace_fund_flows",
        "description": (
            "Find transfer paths from an account to merchants in high-risk countries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "pattern": "^ACC-[A-Za-z0-9_-]{1,60}$",
                }
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "investigate_account",
        "description": (
            "Run the full deterministic risk analysis, returning graph signals, "
            "watchlist matches, score, Cypher evidence, and an SAR draft."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "pattern": "^ACC-[A-Za-z0-9_-]{1,60}$",
                }
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    },
]

_TOOL_FUNCTIONS: dict[str, Callable[[str], dict[str, Any]]] = {
    "get_account_context": get_account_context,
    "trace_fund_flows": trace_fund_flows,
    "investigate_account": investigate_account,
}

SYSTEM_PROMPT = """You are AegisGraph-Agent, an AML investigation assistant.
Use only the approved graph tools to obtain evidence before drawing conclusions.
Treat scores and graph signals as investigation leads, not proof of criminal conduct.
State what the graph shows, identify uncertainty, do not invent missing facts, and
recommend qualified human review. Do not request or attempt writes to the graph.
"""


class AgentConfigurationError(RuntimeError):
    """Raised when the hosted LLM has not been configured."""


def dispatch_investigation_tool(name: str, tool_input: Any) -> dict[str, Any]:
    tool = _TOOL_FUNCTIONS.get(name)
    if tool is None:
        raise ValueError(f"Unsupported investigation tool: {name}")

    if not isinstance(tool_input, dict):
        raise ValueError("Tool input must be an object")
    account_id = tool_input.get("account_id")
    if not isinstance(account_id, str) or not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ValueError("account_id must be a valid ACC- identifier")
    if set(tool_input) != {"account_id"}:
        raise ValueError("Unexpected tool input fields")
    return tool(account_id)


def run_agent(account_id: str) -> dict[str, Any]:
    """Let Anthropic select read-only graph tools and summarize their evidence."""
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ValueError("account_id must be a valid ACC- identifier")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AgentConfigurationError(
            "Set ANTHROPIC_API_KEY locally to enable hosted AI tool-calling."
        )

    client = Anthropic()
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": (
                f"Investigate account {account_id}. Use graph tools to collect "
                "supporting evidence, then explain the findings for human review."
            ),
        }
    ]
    tool_results: list[dict[str, Any]] = []
    tool_calls = 0
    response_text = ""

    for _ in range(MAX_AGENT_TURNS):
        response = client.messages.create(
            model=model,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        response_text = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        if not tool_uses:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_outputs: list[ToolResultBlockParam] = []
        for tool_use in tool_uses:
            tool_calls += 1
            if tool_calls > MAX_TOOL_CALLS:
                raise RuntimeError("Agent exceeded the approved tool-call limit")
            output = dispatch_investigation_tool(tool_use.name, tool_use.input)
            tool_results.append({"tool": tool_use.name, "result": output})
            tool_outputs.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(output, ensure_ascii=False, default=str),
                }
            )
        messages.append({"role": "user", "content": tool_outputs})
    else:
        raise RuntimeError("Agent exceeded the maximum reasoning turns")

    if not tool_results:
        raise RuntimeError("Agent returned without using graph investigation tools")

    return {
        "account_id": account_id,
        "model": model,
        "response": response_text,
        "tools_called": [result["tool"] for result in tool_results],
        "tool_results": tool_results,
        "human_review_required": True,
    }
