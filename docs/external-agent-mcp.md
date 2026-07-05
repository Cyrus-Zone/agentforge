# External Agent MCP Calling

AgentForge exposes published marketplace tools and agents through HTTP endpoints that are shaped for MCP-style discovery and invocation.

## Endpoints

- `GET /mcp/tools` lists callable marketplace tools, agent runners, schemas, examples, and B.AI-ready payment terms.
- `GET /mcp/manifest` returns packaging metadata for an external client or marketplace listing.
- `POST /mcp/call` invokes one registered call by name.

## Call A Marketplace Tool

```json
{
  "tool": "call_marketplace_tool",
  "caller": "external-agent",
  "arguments": {
    "tool_id": "eth-sentiment-lab",
    "input": {
      "symbol": "ETH/USDT",
      "timeframe": "60min"
    }
  }
}
```

The response includes a structured result, the tool input, cost, traceability, and a B.AI-ready `payment` object. The payment object is an unsubmitted simulation intent.

## Run A Marketplace Agent

```json
{
  "tool": "run_marketplace_agent",
  "caller": "external-agent",
  "arguments": {
    "agent_id": "eth-news-agent",
    "input": {
      "symbol": "ETH/USDT",
      "mode": "paper"
    }
  }
}
```

The response wraps the normal workflow run result, including node traces, summary, and payment intent metadata. Agent execution remains paper trading only.

## B.AI-Ready Payment Fields

Marketplace items and traces include:

- `rail`: `B.AI-ready`
- `intent_id`: deterministic simulation reference for the call or run
- `status`: `not_submitted`
- `unit_price_usd`, `quantity`, and `total_usd`
- `creator_amount_usd` and `platform_amount_usd`
- `settlement_asset`: `BAI`
- `money_movement`: `disabled`

These fields are designed to show how creator revenue sharing would be attached to tool and agent calls. AgentForge does not create, sign, submit, or settle real payments.

## Stdio Sketch

`backend/app/mcp_server.py` is a dependency-free sketch for mapping the same contract to stdin/stdout:

```powershell
cd C:\Users\Crypto\Desktop\cofy\backend
'{"tool":"list_marketplace_tools","arguments":{}}' | py -3 -m app.mcp_server
```

It accepts one JSON request per line and writes one JSON response per line. It is intentionally small so an official MCP SDK server can replace it later without changing the marketplace contract.
