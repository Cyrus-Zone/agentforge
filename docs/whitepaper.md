# AgentForge Whitepaper

## Abstract

AgentForge is a visual AI trading workflow platform for composing, tracing, backtesting, sharing, and calling trading intelligence. It turns trading agents and specialized analysis tools into observable workflow assets. Users can build reusable tools, connect them into complete trading agents, evaluate them with historical market data, inspect every decision step, and expose published capabilities to external agents through MCP-shaped endpoints.

The core thesis is simple: AI trading systems should not be opaque. Every trading decision should be explainable through its data inputs, reasoning outputs, risk controls, execution path, costs, and revenue splits. AgentForge provides that layer of traceability while also creating a marketplace where useful tools and complete agents can be reused.

## 1. Problem

AI trading tools are becoming easier to create, but most of them still suffer from several structural problems.

First, many trading bots are black boxes. They may show a profit curve, trade history, or win rate, but they do not show which signals caused a decision or what intermediate reasoning happened before execution.

Second, trading intelligence is hard to reuse. A trader may create a strong sentiment analyzer, risk checker, or market regime detector, but that capability usually stays locked inside one script or one private bot.

Third, evaluation is fragmented. Tool quality and full-strategy quality are often measured together, making it hard to understand whether performance came from a useful signal, a weak risk model, or a lucky market window.

Fourth, external AI agents need structured interfaces. If an agent wants to call a market analysis tool, it needs discoverable schemas, reliable outputs, and traceable responses.

AgentForge addresses these issues by treating every trading capability as a composable, measurable, traceable workflow unit.

## 2. Target Users

AgentForge is designed for several groups:

- **Crypto traders** who want to build and test trading strategies without losing visibility into how decisions are made.
- **AI agent builders** who need callable trading tools with structured inputs and outputs.
- **Quantitative strategy creators** who want to evaluate both individual signals and full workflows.
- **Tool developers** who want to publish reusable components such as sentiment scoring, risk checks, and signal filters.
- **Teams and marketplaces** that need revenue attribution across tool authors, agent publishers, and the platform.

## 3. Product Vision

AgentForge aims to become an execution and infrastructure layer for AI trading intelligence.

For human users, it provides a visual builder where trading workflows can be composed from nodes such as market data, news analysis, sentiment scoring, risk checks, conditions, and paper trade execution.

For external agents, it exposes marketplace tools and complete agents through MCP-shaped endpoints. This means an outside agent can discover available capabilities, inspect schemas, call a published tool, or run a published paper-trading agent.

The long-term goal is a marketplace where trading intelligence is not only created and used, but also measured, audited, shared, and monetized.

## 4. Core Concepts

### Tool

A tool is a focused capability. Examples include ETH sentiment analysis, volatility regime detection, position sizing, or risk validation. A tool can be backtested independently and reused by multiple workflows.

### Agent

An agent is a complete workflow made from multiple nodes and tools. It can combine market data, news context, analysis, risk logic, and execution. An agent can be published as a finished strategy that others can run or call.

### Workflow

A workflow is a directed graph of nodes. Each node receives structured input, performs one step, and returns structured output. The backend executes the graph in topological order and records traces for every node.

### Trace

A trace is the audit record of a node execution. It includes input, output, status, latency, cost, creator split, platform split, and identifiers for later inspection.

### Marketplace

The marketplace lists reusable tools and complete agents. Each item has metadata, pricing intent, schemas, examples, and callable integration details.

## 5. Core Features

### Visual Workflow Builder

Users can compose trading workflows by placing nodes, connecting them, and configuring each step. The builder supports market data, news, LLM-style analysis, sentiment tools, risk checks, conditions, execution, and terminal output.

### Full-Chain Traceability

Every workflow run records the complete path from data input to final result. Users can inspect what each node received, what it produced, how long it took, how much it cost, and which marketplace contributor is attributed.

### Tool-Level Backtesting

Tool backtesting evaluates a single reusable capability, such as a sentiment analyzer. This helps users understand whether a tool produces useful signals before importing it into a larger strategy.

### Agent-Level Backtesting

Agent backtesting evaluates the full workflow over historical candles and archived context. The output includes performance metrics, selected market context, and node-level traces.

### Callable Marketplace

Published tools and agents can be called through HTTP endpoints shaped for MCP-style discovery and invocation. This allows external agents to use AgentForge as trading intelligence infrastructure.

### Revenue Attribution

Marketplace items include revenue-share metadata. A complete agent can route value to tool authors, the agent publisher, and the platform. In the current repository, payment fields are simulation intent metadata only; no real money movement is performed.

## 6. Example Workflow

```text
HTX Market Data
  -> News Tool
  -> Sentiment Tool
  -> Risk Check
  -> HTX Paper Trade
  -> End
```

In this flow, market data provides candles and price context. News adds narrative context. Sentiment analysis produces a directional score and confidence. Risk checks validate sizing and downside limits. Paper trade execution simulates an order. The final node summarizes the result.

A user can then open the run logs and inspect each step rather than trusting a single final answer.

## 7. Technical Architecture

AgentForge is built as a lightweight full-stack application.

```text
React + TypeScript frontend
  Visual workflow builder
  Marketplace UI
  Backtesting UI
  Run logs and trace inspection

Starlette backend
  Workflow execution
  Marketplace endpoints
  Backtesting logic
  MCP-shaped tool discovery and calls

SQLite persistence
  Run records
  Node traces

HTX public market data
  Candle retrieval
  Fallback sample data for local stability
```

The frontend uses React Flow for node-based editing. The backend uses Starlette for HTTP routes and SQLite for local persistence. Market data is fetched from HTX public APIs when available, with local fallback behavior for stable review.

## 8. External Agent Interface

AgentForge exposes MCP-shaped HTTP endpoints:

- `GET /mcp/tools` lists callable tools, agent runners, schemas, examples, and payment-intent metadata.
- `GET /mcp/manifest` returns marketplace metadata for external clients.
- `POST /mcp/call` invokes a registered marketplace tool or agent.

This design lets external agents discover and call AgentForge marketplace capabilities without using the visual interface.

## 9. Backtesting And Auditability

AgentForge separates signal evaluation from full-strategy evaluation.

Tool backtesting asks whether a single tool is useful. Agent backtesting asks whether the assembled strategy works as a complete workflow. Both produce traceable outputs so users can investigate why a backtest passed or failed.

This approach supports better iteration. A weak strategy can be debugged by inspecting individual nodes rather than rewriting the entire workflow.

## 10. Marketplace And Incentives

The marketplace model encourages specialists to contribute reusable trading intelligence. One user may be strong at sentiment analysis, another at risk modeling, and another at assembling strategies. AgentForge allows these contributions to be composed and attributed.

Example revenue path:

```text
Sentiment tool author -> earns from tool calls
Risk tool author      -> earns from risk-check calls
Agent publisher       -> earns from complete agent runs
Platform              -> earns a platform split
```

The current implementation records pricing and split metadata as simulation intent fields. This prepares the data model for future settlement integration while keeping the repository safe for local review.

## 11. Current Implementation Status

The repository currently includes:

- Visual workflow builder.
- Marketplace for tools and complete agents.
- Workflow execution engine.
- Node-level traces.
- Tool and agent backtesting.
- HTX market data integration with fallback sample data.
- SQLite run and trace persistence.
- MCP-shaped HTTP endpoints.
- Static frontend served by the backend.

Trading execution is paper trading only. Historical news context is represented by archived local sample data. LLM-style analysis is deterministic logic for reproducible local review.

## 12. Roadmap

Potential next steps include:

- Official MCP server packaging.
- Real historical news provider integration.
- Live LLM provider support with model selection.
- Strategy versioning and comparison.
- Richer risk engines and portfolio constraints.
- Permissioned marketplace publishing.
- On-chain or payment-rail settlement integration.
- Team workspaces and review workflows.

## 13. Conclusion

AgentForge makes AI trading workflows more transparent, testable, reusable, and callable. Its main contribution is not only visual composition, but full-chain accountability: every trading decision can be traced back through its data, tools, reasoning outputs, costs, and revenue attribution.

By combining workflow building, backtesting, marketplace publishing, and external-agent invocation, AgentForge provides a foundation for a more open and auditable trading intelligence ecosystem.
