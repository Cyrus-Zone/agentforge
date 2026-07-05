"""
Dependency-free MCP stdio sketch for AgentForge.

The production app uses HTTP endpoints:
- GET /mcp/tools
- GET /mcp/manifest
- POST /mcp/call

This module shows the same marketplace contract over stdin/stdout so an MCP
client wrapper can be added without changing the marketplace contract. It
accepts one JSON request per line and writes one JSON response per line.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any, Dict

from .main import WorkflowPayload, execute_workflow, marketplace_items, payment_intent


TOOLS = [
    {
        "name": "list_marketplace_tools",
        "description": "List published AgentForge tools.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "call_marketplace_tool",
        "description": "Call a published AgentForge marketplace tool.",
        "input_schema": {
            "type": "object",
            "properties": {"tool_id": {"type": "string"}, "input": {"type": "object"}},
            "required": ["tool_id", "input"],
        },
    },
    {
        "name": "list_marketplace_agents",
        "description": "List published AgentForge agents.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_marketplace_agent",
        "description": "Run a published AgentForge paper-trading agent.",
        "input_schema": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}, "input": {"type": "object"}},
            "required": ["agent_id"],
        },
    },
]


async def handle_call(message: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(message.get("tool") or message.get("name") or "")
    arguments = message.get("arguments") or {}
    items = marketplace_items()

    if tool_name in {"tools/list", "list_tools"}:
        return {"tools": TOOLS}

    if tool_name == "list_marketplace_tools":
        return {"content": [item for item in items if item["type"] == "tool"]}

    if tool_name == "list_marketplace_agents":
        return {"content": [item for item in items if item["type"] == "agent"]}

    if tool_name == "call_marketplace_tool":
        tool_id = arguments.get("tool_id")
        item = next((entry for entry in items if entry["id"] == tool_id and entry["type"] == "tool"), None)
        if not item:
            return {"error": {"code": "not_found", "message": "Tool not found"}}
        call_id = f"stdio_call_{uuid.uuid4().hex[:8]}"
        return {
            "id": call_id,
            "type": "tool_result",
            "content": {
                "tool_id": tool_id,
                "input": arguments.get("input", {}),
                "result": {
                    "sentiment": "bullish",
                    "confidence": 0.76,
                    "drivers": ["ETF inflow expectations", "rising spot volume", "positive funding reset"],
                },
                "payment": payment_intent(item, call_id),
                "traceable": True,
            },
        }

    if tool_name == "run_marketplace_agent":
        agent_id = arguments.get("agent_id")
        item = next((entry for entry in items if entry["id"] == agent_id and entry["type"] == "agent"), None)
        if not item or not item.get("workflow"):
            return {"error": {"code": "not_found", "message": "Agent not found"}}
        result = await execute_workflow(WorkflowPayload(**item["workflow"]), mode="run")
        result["summary"]["payment"] = payment_intent(item, result["run_id"])
        return {"id": result["run_id"], "type": "agent_run_result", "content": result}

    return {"error": {"code": "unknown_tool", "message": f"Unknown tool: {tool_name}"}}


async def run_stdio() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = await handle_call(message)
        except Exception as exc:
            response = {"error": {"code": "internal_error", "message": str(exc)}}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
