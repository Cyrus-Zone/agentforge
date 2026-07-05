# AgentForge Demo Guide

This guide shows how to present AgentForge as a working product: a visual AI trading workflow platform with traceable execution, backtesting, marketplace reuse, and external-agent calls.

## Demo Goal

Show that AgentForge can:

- Build an AI trading workflow visually.
- Run the workflow and inspect every node result.
- Backtest both a full agent and an individual marketplace tool.
- Publish and reuse trading tools and complete agents.
- Expose marketplace capabilities to external agents through MCP-shaped endpoints.

## Local Setup

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

## 3-Minute Product Walkthrough

### 1. Open The Workspace

Start at the main interface and show the available sections: workspace, builder, logs, marketplace, backtesting, and MCP tools.

Key message:

```text
AgentForge lets users build, test, trace, share, and call AI trading workflows.
```

### 2. Show The Visual Workflow

Open the builder and show a trading chain:

```text
HTX Market Data -> News Tool -> Sentiment Analysis -> Risk Check -> HTX Paper Trade
```

Explain that each node is configurable and that the workflow is not a hidden script. It is a visible decision path.

### 3. Run The Agent

Click `Run Agent`.

Show that the workflow produces a structured result and creates node-level logs.

Key message:

```text
The final result is only one layer. The important part is that every intermediate decision is recorded.
```

### 4. Inspect Logs

Open `Logs` and click individual rows.

Point out:

- Node status.
- Input.
- Output.
- Duration.
- Cost.
- Creator split.
- Platform split.

Key message:

```text
AgentForge makes trading decisions auditable from market data to execution.
```

### 5. Backtest The Full Workflow

Open the backtest flow and run a chain backtest.

Show:

- Selected candle window.
- Historical market context.
- Selected news context.
- Return, win rate, drawdown, or equity curve.
- Traceable node outputs.

Key message:

```text
Users can evaluate the full agent before trusting it.
```

### 6. Backtest A Marketplace Tool

Open the marketplace and select a tool such as `ETH Sentiment Lab`.

Run a tool-level backtest.

Key message:

```text
AgentForge separates tool quality from full-strategy quality, so users can test a signal before importing it.
```

### 7. Show External-Agent Calling

Open the MCP tools view or use the API commands below.

Key message:

```text
Published tools and agents are not locked inside the UI. External agents can discover and call them through structured endpoints.
```

## API Demo

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

List marketplace items:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/marketplace
```

Discover callable tools:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/mcp/tools
```

Read the marketplace manifest:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/mcp/manifest
```

Backtest a marketplace tool:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/backtests/tool `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"item_id":"eth-sentiment-lab","symbol":"ETH/USDT","window":"30d"}'
```

Call a marketplace tool as an external agent:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/mcp/call `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"tool":"call_marketplace_tool","caller":"external-agent","arguments":{"tool_id":"eth-sentiment-lab","input":{"symbol":"ETH/USDT","timeframe":"60min"}}}'
```

Run a published paper-trading agent:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/mcp/call `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"tool":"run_marketplace_agent","caller":"external-agent","arguments":{"agent_id":"eth-news-agent","input":{"symbol":"ETH/USDT","mode":"paper"}}}'
```

## What To Emphasize

- AgentForge is a workflow platform, not only a trading bot.
- The marketplace supports both reusable tools and complete agents.
- Backtesting is available at both tool and workflow levels.
- Every run produces traceable node-level logs.
- External agents can call published capabilities through structured endpoints.
- Payment fields are simulation intent metadata only; no real money movement is performed.

## Current Product Boundaries

- Trading execution is paper trading only.
- HTX candles use public market data when available.
- Historical news context uses archived local sample data.
- LLM-style analysis is deterministic for stable local review.
- MCP support is implemented as HTTP endpoints shaped for discovery and invocation.
