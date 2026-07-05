# AgentForge

AgentForge is a visual, composable, measurable, backtestable, shareable, and callable AI trading workflow platform.

It helps users build trading intelligence as reusable tools or complete agents, inspect every decision step, evaluate performance with historical data, and expose published capabilities to external agents through MCP-shaped endpoints.

## Documents

- [Whitepaper](docs/whitepaper.md)
- [Demo Guide](DEMO.md)
- [External Agent MCP Calling](docs/external-agent-mcp.md)

## What Problem It Solves

AI trading agents often behave like black boxes. A strategy may show profit or loss, but users cannot easily answer:

- Which signal caused the trade?
- What market data, news, or tool output was used?
- Did the risk check pass or fail?
- How much did each step cost?
- Could this tool or full strategy have worked on historical data?
- Can another agent call this tool safely and get structured output?

AgentForge makes each trading workflow observable from end to end. Every node records its input, output, reasoning result, latency, cost, creator split, and platform split, so a user can audit not only the final trade result but also the path that produced it.

## Core Idea

AgentForge has two connected layers:

1. **Workflow Builder**
   Users visually compose AI trading workflows from market data, news, sentiment, risk, condition, execution, and output nodes.

2. **Callable Marketplace**
   Published tools and complete agents become reusable marketplace items. They can be imported into other workflows or called by external agents through MCP-shaped endpoints.

The platform is not only an interface for humans to build agents. It is also infrastructure that lets other agents call trading tools and finished workflows as structured services.

## What Users Can Do

### Create Tools

Users can build a focused trading capability, such as an ETH sentiment analyzer, publish it to the marketplace, and allow other workflows or external agents to call it.

### Create Complete Agents

Users can connect multiple tools into a full trading strategy, for example:

```text
HTX Market Data -> News Tool -> Sentiment Analysis -> Risk Check -> HTX Paper Trade
```

The complete workflow can be published as a ready-to-run agent.

### Use Marketplace Tools

Users can import published tools into their own workflows instead of rebuilding every capability from scratch.

### Use Published Agents

Users can run a finished agent directly and inspect the full execution trace behind the result.

### Backtest Tools And Agents

AgentForge supports both tool-level and workflow-level backtesting:

- Tool backtest: measure whether a single tool produces useful signals.
- Agent backtest: measure whether a full strategy performs over historical candles and archived news snapshots.

Each backtest includes traceable node-level inputs and outputs, not just a summary metric.

## Full-Chain Traceability

Traceability is the core product principle.

A normal trading system may only show final performance. AgentForge shows how the result was produced:

```text
Node 1: Market Data
  Input: ETH/USDT, 60min, 100 candles
  Output: price, candles, trend snapshot

Node 2: News Tool
  Input: ETH market topic
  Output: archived news snapshot and market context

Node 3: Sentiment Tool
  Input: market data and news context
  Output: sentiment, confidence, drivers

Node 4: Risk Check
  Input: suggested action, confidence, volatility, position config
  Output: approved or rejected, stop loss, target, sizing notes

Node 5: HTX Paper Trade
  Input: approved action and quote size
  Output: simulated order, fill price, execution summary
```

For every node, the platform records:

- Input
- Output
- Status
- Latency
- Cost
- Creator revenue split
- Platform split
- Run and trace identifiers

This makes each trade auditable, reproducible, and easier to improve.

## Revenue Sharing Model

Marketplace tools and agents include revenue-share metadata.

For example, a complete agent may use three marketplace tools:

```text
Sentiment tool author      -> earns from each tool call
Risk tool author           -> earns from each tool call
Agent publisher            -> earns from complete agent runs
Platform                   -> earns a platform split
```

The more useful a tool is, the more often it can be reused across workflows and external calls. This creates an incentive loop for contributors to publish high-quality trading intelligence.

Payment fields in this repository are simulation intent metadata only. No real money movement is performed.

## Implemented Features

- Visual workflow builder with draggable nodes and visible connections.
- Configurable trading nodes:
  - HTX Market Data
  - News Tool
  - LLM Analysis
  - Sentiment Tool
  - Risk Check
  - Condition
  - HTX Paper Trade
  - End
- Workflow execution engine with topological ordering.
- Node-level execution logs with input, output, status, duration, cost, and split data.
- Tool-level backtesting.
- Agent workflow backtesting.
- Marketplace for tools and complete agents.
- MCP-shaped HTTP endpoints:
  - `GET /mcp/tools`
  - `GET /mcp/manifest`
  - `POST /mcp/call`
- SQLite persistence for runs and node traces.
- HTX public market API integration with fallback sample data.
- Static frontend served by the backend for a simple local review flow.

## Architecture

```text
Frontend
  React + TypeScript + React Flow
  Visual workflow builder, logs, marketplace, backtesting UI

Backend
  Starlette + SQLite
  Workflow execution, traces, marketplace data, MCP-shaped endpoints

Market Data
  HTX public candles with local fallback data

External Agent Interface
  HTTP endpoints shaped for MCP-style tool discovery and invocation
```

## Run Locally

Install backend dependencies:

```powershell
cd C:\Users\Crypto\Desktop\cofy\backend
py -3 -m pip install -r requirements.txt
```

Start the backend:

```powershell
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

## Rebuild The Frontend

The repository includes a built frontend in `static/` so the backend can serve the app directly. If frontend code changes, rebuild and copy the output:

```powershell
cd C:\Users\Crypto\Desktop\cofy\frontend
npm install
npm run build
Copy-Item -Path .\dist\* -Destination ..\static -Recurse -Force
```

## API Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/marketplace
Invoke-RestMethod http://127.0.0.1:8000/mcp/tools
Invoke-RestMethod http://127.0.0.1:8000/mcp/manifest
```

Tool backtest:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/backtests/tool `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"item_id":"eth-sentiment-lab","symbol":"ETH/USDT","window":"30d"}'
```

External agent calls a marketplace tool:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/mcp/call `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"tool":"call_marketplace_tool","caller":"external-agent","arguments":{"tool_id":"eth-sentiment-lab","input":{"symbol":"ETH/USDT","timeframe":"60min"}}}'
```

External agent runs a published paper-trading agent:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/mcp/call `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"tool":"run_marketplace_agent","caller":"external-agent","arguments":{"agent_id":"eth-news-agent","input":{"symbol":"ETH/USDT","mode":"paper"}}}'
```

See [docs/external-agent-mcp.md](docs/external-agent-mcp.md) for the HTTP contract, stdio sketch, and payment-intent fields.
