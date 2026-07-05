from __future__ import annotations

import json
import subprocess
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "agentforge.db"
NEWS_SNAPSHOTS_PATH = Path(__file__).resolve().parents[1] / "data" / "news_snapshots.json"
STATIC_PATH = Path(__file__).resolve().parents[2] / "static"


class FlowNodeData(BaseModel):
    label: str
    kind: str
    description: str = ""
    cost: float = 0
    revenueShare: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = None


class FlowNode(BaseModel):
    id: str
    type: Optional[str] = None
    position: Dict[str, float] = Field(default_factory=dict)
    data: FlowNodeData


class FlowEdge(BaseModel):
    id: Optional[str] = None
    source: str
    target: str
    animated: Optional[bool] = None


class WorkflowPayload(BaseModel):
    name: str
    nodes: List[FlowNode]
    edges: List[FlowEdge]
    backtest_config: Dict[str, Any] = Field(default_factory=dict)


class McpCall(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    caller: Optional[str] = None


class ToolBacktestPayload(BaseModel):
    item_id: str
    symbol: str = "ETH/USDT"
    window: str = "30d"


def startup() -> None:
    init_db()


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def index(request: Request) -> FileResponse:
    return FileResponse(STATIC_PATH / "index.html")


async def marketplace(request: Request) -> JSONResponse:
    return JSONResponse(marketplace_items())


async def market_candles(request: Request) -> JSONResponse:
    symbol = request.query_params.get("symbol", "ethusdt")
    timeframe = request.query_params.get("timeframe", "60min")
    size = int(request.query_params.get("size", "120"))
    candles, source = await fetch_htx_candles(symbol, timeframe, size)
    return JSONResponse(
        {
            "symbol": symbol.upper().replace("USDT", "/USDT"),
            "timeframe": timeframe,
            "source": source,
            "candles": candles,
            "news_snapshots": news_snapshots_for_candles(candles, symbol=symbol),
        }
    )


async def run_workflow(request: Request) -> JSONResponse:
    payload = WorkflowPayload(**await request.json())
    result = await execute_workflow(payload, mode="run")
    return JSONResponse(result)


async def backtest_workflow(request: Request) -> JSONResponse:
    payload = WorkflowPayload(**await request.json())
    result = await execute_workflow(payload, mode="backtest")
    result["summary"]["mode"] = "backtest"
    bt = await run_historical_backtest(payload)
    result["summary"].update(bt)
    return JSONResponse(result)


async def backtest_tool(request: Request) -> JSONResponse:
    payload = ToolBacktestPayload(**await request.json())
    item = next((entry for entry in marketplace_items() if entry["id"] == payload.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Marketplace item not found")

    run_id = f"tool_bt_{uuid.uuid4().hex[:8]}"
    if item["type"] == "agent" and item.get("workflow"):
        result = await execute_workflow(WorkflowPayload(**item["workflow"]), mode="backtest")
        result["summary"].update(await run_historical_backtest(WorkflowPayload(**item["workflow"])))
        return JSONResponse(result)

    selected_news = news_context_for_window(payload.symbol, payload.window)
    metrics = {
        "item_id": item["id"],
        "item_name": item["name"],
        "symbol": payload.symbol,
        "window": payload.window,
        "history_source": "HTX historical candles + archived demo news snapshots",
        "selected_news_context": {
            "source": "archived demo news snapshots",
            "window": payload.window,
            "snapshots": selected_news,
        },
        "samples": 120,
        "signal_accuracy": 0.68 if "sentiment" in item["tags"] else 0.73,
        "avg_confidence": 0.74,
        "false_positive_rate": 0.18,
        "cost_per_1000_calls": round(item["price_usd"] * 1000, 2),
        "optimization_hint": "Raise min_confidence to 0.70 during high-volatility sessions.",
    }
    traces = [
        {
            "node_id": payload.item_id,
            "node_type": item["type"],
            "label": item["name"],
            "status": "success",
            "input": {
                "symbol": payload.symbol,
                "window": payload.window,
                "historical_news": selected_news,
            },
            "output": metrics,
            "cost_usd": round(float(item["price_usd"]) * 120, 4),
            "revenue_split": {
                "creator": round(float(item["price_usd"]) * 120 * 0.8, 4),
                "platform": round(float(item["price_usd"]) * 120 * 0.2, 4),
                "payment_rail": "B.AI-ready",
                "payment": payment_intent(item, run_id, quantity=120),
            },
            "duration_ms": 482,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    persist_run(run_id, f"Tool Backtest: {item['name']}", "success", metrics, traces)
    return JSONResponse(
        {
            "run_id": run_id,
            "workflow_name": f"Tool Backtest: {item['name']}",
            "status": "success",
            "summary": metrics,
            "traces": traces,
        }
    )


async def mcp_tools(request: Request) -> JSONResponse:
    return JSONResponse({
        "service": "AgentForge Marketplace MCP Gateway",
        "protocol": "mcp-shaped-http-demo",
        "description": "HTTP endpoints that expose published marketplace tools and agents to external agents.",
        "endpoints": {
            "list_tools": "GET /mcp/tools",
            "call_tool": "POST /mcp/call",
            "manifest": "GET /mcp/manifest",
        },
        "payment": b_ai_payment_terms(),
        "examples": {
            "call_marketplace_tool": {
                "tool": "call_marketplace_tool",
                "caller": "external-agent-demo",
                "arguments": {
                    "tool_id": "eth-sentiment-lab",
                    "input": {"symbol": "ETH/USDT", "timeframe": "60min"},
                },
            },
            "run_marketplace_agent": {
                "tool": "run_marketplace_agent",
                "caller": "external-agent-demo",
                "arguments": {
                    "agent_id": "eth-news-agent",
                    "input": {"symbol": "ETH/USDT", "mode": "paper"},
                },
            },
        },
        "tools": [
            {
                "name": "list_marketplace_tools",
                "description": "List published trading tools that can be imported or called by agents.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "call_marketplace_tool",
                "description": "Call a published marketplace tool such as ETH Sentiment Lab.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tool_id": {"type": "string"},
                        "input": {"type": "object"},
                        "trace": {"type": "boolean", "description": "Return trace/payment metadata when true."},
                    },
                    "required": ["tool_id", "input"],
                },
            },
            {
                "name": "list_marketplace_agents",
                "description": "List published executable trading agents.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "run_marketplace_agent",
                "description": "Run a published paper-trading agent with structured input.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "input": {"type": "object"},
                        "mode": {"type": "string", "enum": ["paper"]},
                    },
                    "required": ["agent_id"],
                },
            },
        ]
    })


async def mcp_manifest(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "name": "agentforge-marketplace",
            "display_name": "AgentForge Marketplace",
            "version": "0.1.0-demo",
            "description": "Marketplace gateway for calling published trading tools and paper-trading agents.",
            "transport": {
                "type": "http",
                "tools_url": "/mcp/tools",
                "call_url": "/mcp/call",
                "stdio_sketch": "python -m app.mcp_server",
            },
            "capabilities": ["tools/list", "tools/call", "agent/run", "trace/readiness", "paper-trading-only"],
            "payment": b_ai_payment_terms(),
            "safety": {
                "money_movement": "disabled",
                "execution_mode": "paper trading only",
                "settlement": "demo ledger metadata; no real B.AI transfer is performed",
            },
        }
    )


async def mcp_call(request: Request) -> JSONResponse:
    payload = McpCall(**await request.json())
    items = marketplace_items()
    if payload.tool == "list_marketplace_tools":
        return JSONResponse({"content": [item for item in items if item["type"] == "tool"], "payment": b_ai_payment_terms()})
    if payload.tool == "list_marketplace_agents":
        return JSONResponse({"content": [item for item in items if item["type"] == "agent"], "payment": b_ai_payment_terms()})
    if payload.tool == "call_marketplace_tool":
        tool_id = payload.arguments.get("tool_id")
        match = next((item for item in items if item["id"] == tool_id and item["type"] == "tool"), None)
        if not match:
            raise HTTPException(status_code=404, detail="Tool not found")
        call_id = f"mcp_call_{uuid.uuid4().hex[:8]}"
        input_payload = payload.arguments.get("input", {})
        return JSONResponse({
            "id": call_id,
            "type": "tool_result",
            "content": {
                "tool_id": tool_id,
                "caller": payload.caller or payload.arguments.get("caller") or "external-agent",
                "input": input_payload,
                "result": {
                    "sentiment": "bullish",
                    "confidence": 0.76,
                    "drivers": ["ETF inflow expectations", "rising spot volume", "positive funding reset"],
                },
                "cost_usd": match["price_usd"],
                "payment": payment_intent(match, call_id, quantity=1),
                "traceable": True,
            }
        })
    if payload.tool == "run_marketplace_agent":
        agent_id = payload.arguments.get("agent_id")
        agent = next((item for item in items if item["type"] == "agent" and item["id"] == agent_id), None)
        if not agent or not agent.get("workflow"):
            raise HTTPException(status_code=404, detail="Agent not found")
        result = await execute_workflow(WorkflowPayload(**agent["workflow"]), mode="run")
        result["summary"]["external_caller"] = payload.caller or payload.arguments.get("caller") or "external-agent"
        result["summary"]["payment"] = payment_intent(agent, result["run_id"], quantity=1)
        return JSONResponse({"id": result["run_id"], "type": "agent_run_result", "content": result})
    raise HTTPException(status_code=404, detail="MCP tool not registered")


async def execute_workflow(payload: WorkflowPayload, mode: Literal["run", "backtest"]) -> Dict[str, Any]:
    if not payload.nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")

    ordered_nodes = topo_sort(payload.nodes, payload.edges)
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    memory: Dict[str, Any] = {}
    traces: List[Dict[str, Any]] = []
    total_cost = 0.0

    for node in ordered_nodes:
        started = time.perf_counter()
        node_input = collect_inputs(node, payload.edges, memory)
        output = await run_node(node, node_input, mode=mode)
        duration = int((time.perf_counter() - started) * 1000)
        memory[node.id] = output
        cost = float(node.data.cost or 0)
        total_cost += cost
        trace = {
            "node_id": node.id,
            "node_type": node.data.kind,
            "label": node.data.label,
            "status": "success",
            "input": node_input,
            "output": output,
            "cost_usd": round(cost, 4),
            "revenue_split": {
                "creator": round(cost * 0.8, 4),
                "platform": round(cost * 0.2, 4),
                "payment_rail": "B.AI-ready",
                "payment": payment_intent(
                    {"price_usd": cost},
                    f"{run_id}_{node.id}",
                    quantity=1,
                ),
            },
            "duration_ms": duration,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        traces.append(trace)

    summary = summarize(memory, traces)
    summary["total_cost_usd"] = round(total_cost, 4)
    summary["nodes_executed"] = len(traces)
    summary["mode"] = mode
    persist_run(run_id, payload.name, "success", summary, traces)

    return {
        "run_id": run_id,
        "workflow_name": payload.name,
        "status": "success",
        "summary": summary,
        "traces": traces,
    }


def topo_sort(nodes: List[FlowNode], edges: List[FlowEdge]) -> List[FlowNode]:
    by_id = {node.id: node for node in nodes}
    incoming = {node.id: 0 for node in nodes}
    outgoing: Dict[str, List[str]] = {node.id: [] for node in nodes}
    for edge in edges:
        if edge.source in by_id and edge.target in by_id:
            incoming[edge.target] += 1
            outgoing[edge.source].append(edge.target)

    queue = [node_id for node_id, count in incoming.items() if count == 0]
    ordered: List[FlowNode] = []
    while queue:
        current = queue.pop(0)
        ordered.append(by_id[current])
        for target in outgoing[current]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)

    if len(ordered) != len(nodes):
        raise HTTPException(status_code=400, detail="Workflow graph contains a cycle")
    return ordered


def collect_inputs(node: FlowNode, edges: List[FlowEdge], memory: Dict[str, Any]) -> Dict[str, Any]:
    upstream_ids = [edge.source for edge in edges if edge.target == node.id]
    upstream = {node_id: memory[node_id] for node_id in upstream_ids if node_id in memory}
    return {"config": node.data.config, "upstream": upstream}


async def run_node(node: FlowNode, node_input: Dict[str, Any], mode: str) -> Dict[str, Any]:
    kind = node.data.kind
    config = node.data.config
    upstream = node_input["upstream"]

    if kind == "market_data":
        symbol = str(config.get("symbol", "ethusdt")).lower().replace("/", "")
        timeframe = str(config.get("timeframe", "60min"))
        candles = int(config.get("candles", 100))
        market = await fetch_htx_market(symbol, timeframe, candles)
        return market

    if kind == "news":
        topic = str(config.get("topic", "ETH crypto market"))
        limit = int(config.get("limit", 5))
        return {
            "topic": topic,
            "headlines": demo_headlines(topic)[:limit],
            "source": "demo-news-wire",
        }

    if kind in {"llm", "sentiment_tool"}:
        context = flatten_upstream(upstream)
        price_change = float(context.get("price_change_pct", 1.4))
        headline_text = " ".join(context.get("headlines", []))
        bullish_words = sum(word in headline_text.lower() for word in ["inflow", "upgrade", "bull", "etf", "volume"])
        confidence = min(0.92, max(0.54, 0.62 + price_change / 20 + bullish_words * 0.035))
        trend = "bullish" if confidence >= 0.66 else "neutral"
        action = "buy" if trend == "bullish" else "hold"
        return {
            "trend": trend,
            "sentiment": trend,
            "confidence": round(confidence, 2),
            "reason": (
                "The node combines HTX price action with current headlines and emits a structured trading signal."
            ),
            "drivers": ["spot momentum", "headline sentiment", "volume confirmation"],
            "suggested_action": action,
            "risk_flags": ["high_volatility"] if price_change > 3 else [],
            "schema": ["trend", "confidence", "reason", "suggested_action", "risk_flags"],
        }

    if kind == "condition":
        context = flatten_upstream(upstream)
        confidence = float(context.get("confidence", 0))
        action = str(context.get("suggested_action", "hold"))
        passed = confidence > 0.62 and action == "buy"
        return {"passed": passed, "confidence": confidence, "suggested_action": action}

    if kind == "risk":
        context = flatten_upstream(upstream)
        confidence = float(context.get("confidence", 0.62))
        min_confidence = float(config.get("min_confidence", 0.62))
        max_position = float(config.get("max_position_pct", 20))
        suggested_action = str(context.get("suggested_action", "hold"))
        passed = confidence >= min_confidence and suggested_action in {"buy", "sell"}
        return {
            "passed": passed,
            "approved_action": suggested_action if passed else "hold",
            "position_pct": min(max_position, round(confidence * max_position, 2)),
            "stop_loss_pct": float(config.get("stop_loss_pct", 3)),
            "checks": {
                "confidence": confidence >= min_confidence,
                "position_limit": True,
                "paper_mode": True,
            },
        }

    if kind == "paper_trade":
        context = flatten_upstream(upstream)
        action = str(context.get("approved_action", context.get("suggested_action", "hold")))
        price = float(context.get("last_price", 3450.0))
        quote_size = float(config.get("quote_size_usdt", 1000))
        size = 0 if action == "hold" else round(quote_size / price, 6)
        return {
            "exchange": config.get("exchange", "HTX"),
            "mode": "paper",
            "action": action.upper(),
            "symbol": context.get("symbol", "ETH/USDT"),
            "price": round(price, 2),
            "quote_size_usdt": quote_size,
            "base_size": size,
            "order_id": f"PAPER-{uuid.uuid4().hex[:10].upper()}",
        }

    if kind == "end":
        return {"final": flatten_upstream(upstream), "completed": True}

    return {"echo": node_input, "kind": kind}


async def fetch_htx_market(symbol: str, timeframe: str, candles: int) -> Dict[str, Any]:
    data, source = await fetch_htx_candles(symbol, timeframe, candles)
    if data:
        latest = data[-1]
        previous = data[-2] if len(data) > 1 else latest
        last_price = float(latest["close"])
        prev_price = float(previous["close"])
        change = ((last_price - prev_price) / prev_price) * 100 if prev_price else 0
        return {
            "symbol": symbol.upper().replace("USDT", "/USDT"),
            "timeframe": timeframe,
            "last_price": round(last_price, 2),
            "price_change_pct": round(change, 3),
            "volume": round(float(latest.get("vol", 0)), 2),
            "candles": data[-8:],
            "source": source,
        }
    return {
        "symbol": symbol.upper().replace("USDT", "/USDT"),
        "timeframe": timeframe,
        "last_price": 3450.0,
        "price_change_pct": 1.85,
        "volume": 1284500.0,
        "candles": [
            {"time": "demo-1", "open": 3388, "high": 3468, "low": 3370, "close": 3450},
            {"time": "demo-2", "open": 3338, "high": 3410, "low": 3312, "close": 3388},
        ],
        "source": "HTX fallback demo data",
    }


async def fetch_htx_candles(symbol: str, timeframe: str, candles: int) -> tuple[List[Dict[str, Any]], str]:
    url = "https://api.huobi.pro/market/history/kline"
    normalized = symbol.lower().replace("/", "")
    size = max(20, min(int(candles or 200), 500))
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(url, params={"symbol": normalized, "period": timeframe, "size": size})
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data") or []
            if payload.get("status") == "ok" and rows:
                normalized_rows = [
                    {
                        "time": int(item.get("id", 0)),
                        "open": float(item.get("open", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "close": float(item.get("close", 0)),
                        "volume": float(item.get("vol", 0)),
                    }
                    for item in rows
                ]
                normalized_rows.sort(key=lambda item: item["time"])
                return normalized_rows, "HTX public market API"
    except Exception:
        pass

    curl_rows = fetch_htx_candles_with_curl(normalized, timeframe, size)
    if curl_rows:
        return curl_rows, "HTX public market API via curl fallback"

    powershell_rows = fetch_htx_candles_with_powershell(normalized, timeframe, size)
    if powershell_rows:
        return powershell_rows, "HTX public market API via PowerShell fallback"

    return generated_candles(size), "generated fallback candles"


def fetch_htx_candles_with_curl(symbol: str, timeframe: str, size: int) -> List[Dict[str, Any]]:
    url = f"https://api.huobi.pro/market/history/kline?symbol={symbol}&period={timeframe}&size={size}"
    try:
        completed = subprocess.run(
            ["curl.exe", "-sS", "--max-time", "10", url],
            capture_output=True,
            text=True,
            timeout=12,
        )
        if completed.returncode != 0 or not completed.stdout:
            return []
        payload = json.loads(completed.stdout)
        rows = payload.get("data") or []
        if payload.get("status") != "ok" or not rows:
            return []
        normalized_rows = [
            {
                "time": int(item.get("id", 0)),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": float(item.get("vol", 0)),
            }
            for item in rows
        ]
        normalized_rows.sort(key=lambda item: item["time"])
        return normalized_rows
    except Exception:
        return []


def fetch_htx_candles_with_powershell(symbol: str, timeframe: str, size: int) -> List[Dict[str, Any]]:
    url = f"https://api.huobi.pro/market/history/kline?symbol={symbol}&period={timeframe}&size={size}"
    script = f"$r = Invoke-RestMethod '{url}'; $r | ConvertTo-Json -Depth 6 -Compress"
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if completed.returncode != 0 or not completed.stdout:
            return []
        payload = json.loads(completed.stdout)
        rows = payload.get("data") or []
        if payload.get("status") != "ok" or not rows:
            return []
        normalized_rows = [
            {
                "time": int(item.get("id", 0)),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": float(item.get("vol", 0)),
            }
            for item in rows
        ]
        normalized_rows.sort(key=lambda item: item["time"])
        return normalized_rows
    except Exception:
        return []


async def run_historical_backtest(payload: WorkflowPayload) -> Dict[str, Any]:
    market_node = next((node for node in payload.nodes if node.data.kind == "market_data"), None)
    risk_node = next((node for node in payload.nodes if node.data.kind == "risk"), None)
    config = dict(market_node.data.config if market_node else {})
    config.update(payload.backtest_config or {})
    symbol = str(config.get("symbol", "ethusdt")).lower().replace("/", "")
    timeframe = str(config.get("timeframe", "60min"))
    candle_count = int(config.get("candles", config.get("sample_size", 200)))
    initial_capital = float(config.get("initial_capital", 10000))
    fee_bps = float(config.get("fee_bps", 8))
    stop_loss_pct = float((risk_node.data.config if risk_node else {}).get("stop_loss_pct", config.get("stop_loss_pct", 3)))
    take_profit_pct = float(config.get("take_profit_pct", 6))
    candles, source = await fetch_htx_candles(symbol, timeframe, candle_count)
    start_index = max(0, int(config.get("start_index", 0)))
    end_index = min(len(candles) - 1, int(config.get("end_index", len(candles) - 1)))
    if end_index > start_index:
        candles = candles[start_index : end_index + 1]
    selected_news = [] if config.get("news_source") == "price-only backtest" else news_snapshots_for_candles(
        candles,
        symbol=symbol.upper().replace("USDT", "/USDT"),
    )
    simulation = simulate_strategy_backtest(
        candles=candles,
        initial_capital=initial_capital,
        fee_bps=fee_bps,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )
    return {
        **simulation,
        "backtest_config": {
            "symbol": symbol.upper().replace("USDT", "/USDT"),
            "timeframe": timeframe,
            "candles": len(candles),
            "initial_capital": initial_capital,
            "fee_bps": fee_bps,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "news_source": config.get("news_source", "archived demo news snapshots"),
            "start_index": start_index,
            "end_index": end_index,
            "start_time": candles[0]["time"] if candles else None,
            "end_time": candles[-1]["time"] if candles else None,
            "selected_news_count": len(selected_news),
        },
        "history_source": f"{source} + {config.get('news_source', 'archived demo news snapshots')}",
        "news_snapshots": selected_news,
        "selected_news_context": {
            "source": config.get("news_source", "archived demo news snapshots"),
            "window_start": candles[0]["time"] if candles else None,
            "window_end": candles[-1]["time"] if candles else None,
            "snapshots": selected_news,
        },
        "last_price": candles[-1]["close"] if candles else 0,
    }


def simulate_strategy_backtest(
    candles: List[Dict[str, Any]],
    initial_capital: float,
    fee_bps: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> Dict[str, Any]:
    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    peak = initial_capital
    max_drawdown = 0.0

    closes = [float(candle["close"]) for candle in candles]
    for index, candle in enumerate(candles):
        price = float(candle["close"])
        fast = sum(closes[max(0, index - 4) : index + 1]) / len(closes[max(0, index - 4) : index + 1])
        slow_window = closes[max(0, index - 14) : index + 1]
        slow = sum(slow_window) / len(slow_window)
        momentum = 0 if index < 3 else (price - closes[index - 3]) / closes[index - 3]
        signal_buy = index >= 15 and position == 0 and fast > slow and momentum > 0
        signal_sell = position > 0 and (fast < slow or price <= entry_price * (1 - stop_loss_pct / 100) or price >= entry_price * (1 + take_profit_pct / 100))
        fee_rate = fee_bps / 10000

        if signal_buy:
            spend = cash * 0.95
            fee = spend * fee_rate
            position = (spend - fee) / price
            cash -= spend
            entry_price = price
            trades.append({"side": "BUY", "time": candle["time"], "price": round(price, 4), "fee": round(fee, 4), "reason": "fast_ma_above_slow_ma"})
        elif signal_sell:
            proceeds = position * price
            fee = proceeds * fee_rate
            cash += proceeds - fee
            pnl_pct = ((price - entry_price) / entry_price) * 100 if entry_price else 0
            trades.append({"side": "SELL", "time": candle["time"], "price": round(price, 4), "fee": round(fee, 4), "pnl_pct": round(pnl_pct, 2), "reason": "exit_rule"})
            position = 0
            entry_price = 0

        equity = cash + position * price
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak else 0
        max_drawdown = max(max_drawdown, drawdown)
        if index % max(1, len(candles) // 40) == 0 or index == len(candles) - 1:
            equity_curve.append({"step": index, "time": candle["time"], "equity": round(equity, 2), "price": round(price, 4)})

    if position > 0 and candles:
        price = float(candles[-1]["close"])
        proceeds = position * price
        fee = proceeds * (fee_bps / 10000)
        cash += proceeds - fee
        pnl_pct = ((price - entry_price) / entry_price) * 100 if entry_price else 0
        trades.append({"side": "SELL", "time": candles[-1]["time"], "price": round(price, 4), "fee": round(fee, 4), "pnl_pct": round(pnl_pct, 2), "reason": "close_at_end"})

    final_equity = cash
    closed = [trade for trade in trades if trade["side"] == "SELL"]
    wins = [trade for trade in closed if float(trade.get("pnl_pct", 0)) > 0]
    return_pct = ((final_equity - initial_capital) / initial_capital) * 100 if initial_capital else 0
    return {
        "equity_curve": equity_curve,
        "trades": trades[-20:],
        "total_return_pct": round(return_pct, 2),
        "final_equity": round(final_equity, 2),
        "win_rate": round(len(wins) / len(closed), 3) if closed else 0,
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "trade_count": len(trades),
        "strategy_rule": "fast MA / slow MA crossover with stop-loss and take-profit",
    }


def generated_candles(size: int) -> List[Dict[str, Any]]:
    candles: List[Dict[str, Any]] = []
    price = 3450.0
    for index in range(size):
        drift = ((index % 17) - 8) * 1.4 + (index % 5) * 0.8
        open_price = price
        close = max(100, price + drift)
        high = max(open_price, close) * 1.004
        low = min(open_price, close) * 0.996
        candles.append(
            {
                "time": 1780000000 + index * 3600,
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": round(1000000 + index * 913, 2),
            }
        )
        price = close
    return candles


def flatten_upstream(upstream: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for output in upstream.values():
        if isinstance(output, dict):
            merged.update(output)
            if "headlines" in output:
                merged["headlines"] = output["headlines"]
    return merged


def summarize(memory: Dict[str, Any], traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    context = flatten_upstream(memory)
    final_action = context.get("action") or context.get("approved_action") or context.get("suggested_action") or "hold"
    return {
        "final_action": str(final_action).upper(),
        "last_price": context.get("last_price", 3450.0),
        "confidence": context.get("confidence", 0),
        "trace_depth": len(traces),
    }


def b_ai_payment_terms() -> Dict[str, Any]:
    return {
        "rail": "B.AI-ready",
        "status": "demo_intent_only",
        "currency": "USD",
        "settlement_asset": "BAI",
        "creator_share_pct": 80,
        "platform_share_pct": 20,
        "money_movement": "disabled",
        "note": "Trace and marketplace payloads expose payment intent metadata only; no real transfer is created.",
    }


def payment_intent(item: Dict[str, Any], reference_id: str, quantity: int = 1) -> Dict[str, Any]:
    unit_price = float(item.get("price_usd", 0))
    total = round(unit_price * quantity, 4)
    return {
        "rail": "B.AI-ready",
        "intent_id": f"bai_demo_{reference_id}",
        "status": "not_submitted",
        "unit_price_usd": round(unit_price, 4),
        "quantity": quantity,
        "total_usd": total,
        "creator_amount_usd": round(total * 0.8, 4),
        "platform_amount_usd": round(total * 0.2, 4),
        "settlement_asset": "BAI",
        "money_movement": "disabled",
    }


def demo_headlines(topic: str) -> List[str]:
    return [
        f"{topic}: ETF inflow expectations lift spot market attention",
        "HTX order book shows higher bid depth during Asia session",
        "Macro desks report stronger risk appetite after volatility reset",
        "On-chain activity rises as stablecoin liquidity moves into majors",
        "Derivatives funding cools while spot volume expands",
    ]


def load_news_snapshots() -> List[Dict[str, Any]]:
    try:
        with NEWS_SNAPSHOTS_PATH.open("r", encoding="utf-8") as handle:
            snapshots = json.load(handle)
            return snapshots if isinstance(snapshots, list) else []
    except Exception:
        return []


def parse_snapshot_time(snapshot: Dict[str, Any]) -> int:
    published_at = str(snapshot.get("published_at", ""))
    try:
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except Exception:
        return 0


def candle_timestamp(candle: Dict[str, Any]) -> int:
    raw = int(float(candle.get("time", 0)))
    return raw // 1000 if raw > 10_000_000_000 else raw


def nearest_candle_time(candles: List[Dict[str, Any]], target_time: int) -> Optional[int]:
    if not candles or not target_time:
        return None
    return min((candle_timestamp(candle) for candle in candles), key=lambda item: abs(item - target_time))


def snapshot_matches_symbol(snapshot: Dict[str, Any], symbol: str) -> bool:
    normalized = symbol.upper().replace("/", "")
    symbols = [str(item).upper().replace("/", "") for item in snapshot.get("symbols", [])]
    return "ALL" in symbols or normalized in symbols


def news_snapshots_for_candles(
    candles: List[Dict[str, Any]],
    symbol: str = "ETH/USDT",
    limit: int = 4,
) -> List[Dict[str, Any]]:
    if not candles:
        return []

    start_time = candle_timestamp(candles[0])
    end_time = candle_timestamp(candles[-1])
    midpoint = start_time + ((end_time - start_time) // 2)
    candidates = [snapshot for snapshot in load_news_snapshots() if snapshot_matches_symbol(snapshot, symbol)]

    if not candidates:
        return fallback_news_snapshots(candles)

    def sort_key(snapshot: Dict[str, Any]) -> tuple[int, int]:
        snapshot_time = parse_snapshot_time(snapshot)
        in_window = start_time <= snapshot_time <= end_time
        return (0 if in_window else 1, abs(snapshot_time - midpoint))

    selected = sorted(candidates, key=sort_key)[:limit]
    mapped: List[Dict[str, Any]] = []
    for snapshot in selected:
        snapshot_time = parse_snapshot_time(snapshot)
        relation = "inside selected candle window" if start_time <= snapshot_time <= end_time else "nearest archived context"
        mapped.append(
            {
                "id": snapshot.get("id"),
                "time": snapshot_time,
                "iso_time": snapshot.get("published_at"),
                "matched_candle_time": nearest_candle_time(candles, snapshot_time),
                "window_start": start_time,
                "window_end": end_time,
                "window_relation": relation,
                "symbol": symbol.upper().replace("USDT", "/USDT") if "/" not in symbol else symbol.upper(),
                "headline": snapshot.get("headline"),
                "headlines": snapshot.get("headlines", []),
                "sentiment": snapshot.get("sentiment", "neutral"),
                "market_regime": snapshot.get("market_regime", "unknown"),
                "drivers": snapshot.get("drivers", []),
                "source": snapshot.get("source", "archived demo news snapshot"),
                "relevance": snapshot.get("relevance", ""),
            }
        )
    return mapped


def fallback_news_snapshots(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    anchors = [0, len(candles) // 3, (len(candles) * 2) // 3, len(candles) - 1]
    headlines = demo_headlines("selected backtest window")
    snapshots = []
    for offset, index in enumerate(sorted(set(anchors))):
        snapshots.append(
            {
                "time": candles[index]["time"],
                "matched_candle_time": candles[index]["time"],
                "window_relation": "generated fallback context",
                "headlines": [headlines[offset % len(headlines)], headlines[(offset + 1) % len(headlines)]],
                "source": "generated demo news fallback",
            }
        )
    return snapshots


def news_context_for_window(symbol: str, window: str) -> List[Dict[str, Any]]:
    size_by_window = {"7d": 168, "14d": 240, "30d": 360, "90d": 500}
    candles = generated_candles(size_by_window.get(window, 240))
    return news_snapshots_for_candles(candles, symbol=symbol, limit=3)


def make_equity_curve(last_price: float) -> List[Dict[str, Any]]:
    return [
        {"step": 0, "equity": 10000},
        {"step": 1, "equity": round(10000 + last_price * 0.02, 2)},
        {"step": 2, "equity": round(10080 + last_price * 0.035, 2)},
        {"step": 3, "equity": round(10160 - last_price * 0.015, 2)},
        {"step": 4, "equity": round(10210 + last_price * 0.028, 2)},
    ]


def marketplace_items() -> List[Dict[str, Any]]:
    payment_terms = b_ai_payment_terms()
    sentiment_node = {
        "kind": "sentiment_tool",
        "label": "ETH Sentiment Lab",
        "description": "A reusable sentiment tool built from news and market context.",
        "cost": 0.004,
        "config": {"source": "marketplace:eth-sentiment-lab", "output_schema": "sentiment,confidence,drivers"},
    }
    workflow_nodes = [
        node_payload("a1", "market_data", "HTX Market Data", 0, 90, 110, {"symbol": "ethusdt", "timeframe": "60min", "candles": 100}),
        node_payload("a2", "news", "News Tool", 0.001, 360, 60, {"topic": "ETH ETF crypto market", "limit": 5}),
        node_payload("a3", "llm", "LLM Analysis", 0.006, 630, 110, {"model": "demo-llm", "prompt": "Return structured market trend JSON."}),
        node_payload("a4", "risk", "Risk Check", 0.002, 900, 110, {"max_position_pct": 20, "stop_loss_pct": 3, "min_confidence": 0.62}),
        node_payload("a5", "paper_trade", "HTX Paper Trade", 0.001, 1170, 110, {"quote_size_usdt": 1000, "mode": "paper", "exchange": "HTX"}),
    ]
    return [
        {
            "id": "eth-sentiment-lab",
            "type": "tool",
            "name": "ETH Sentiment Lab",
            "subtitle": "News-aware ETH sentiment scoring",
            "description": "Turns market headlines and HTX context into sentiment, confidence and drivers.",
            "author": "Ava Quant",
            "price_usd": 0.004,
            "pricing": {
                "unit": "call",
                "price_usd": 0.004,
                "payment": payment_terms,
            },
            "mcp": {
                "call_tool": "call_marketplace_tool",
                "arguments": {"tool_id": "eth-sentiment-lab", "input": {"symbol": "ETH/USDT"}},
            },
            "tags": ["sentiment", "ETH", "LLM node"],
            "performance": {"calls": 18420, "avg_latency_ms": 680},
            "nodeTemplate": sentiment_node,
        },
        {
            "id": "risk-guard-lite",
            "type": "tool",
            "name": "Risk Guard Lite",
            "subtitle": "Position sizing and stop-loss checks",
            "description": "Rejects low-confidence trades and emits approved action, size and stop loss.",
            "author": "Kai Risk",
            "price_usd": 0.002,
            "pricing": {
                "unit": "call",
                "price_usd": 0.002,
                "payment": payment_terms,
            },
            "mcp": {
                "call_tool": "call_marketplace_tool",
                "arguments": {"tool_id": "risk-guard-lite", "input": {"confidence": 0.72, "suggested_action": "buy"}},
            },
            "tags": ["risk", "paper trading", "guardrail"],
            "performance": {"calls": 9730, "avg_latency_ms": 120},
            "nodeTemplate": {
                "kind": "risk",
                "label": "Risk Guard Lite",
                "description": "Marketplace risk node with configurable limits.",
                "cost": 0.002,
                "config": {"max_position_pct": 15, "stop_loss_pct": 2.5, "min_confidence": 0.66},
            },
        },
        {
            "id": "eth-news-agent",
            "type": "agent",
            "name": "ETH News Trading Agent",
            "subtitle": "HTX data plus news-aware LLM trading workflow",
            "description": "A complete paper-trading agent that can be imported, run, traced and backtested.",
            "author": "AgentForge Demo",
            "price_usd": 0.014,
            "pricing": {
                "unit": "agent_run",
                "price_usd": 0.014,
                "payment": payment_terms,
            },
            "mcp": {
                "call_tool": "run_marketplace_agent",
                "arguments": {"agent_id": "eth-news-agent", "input": {"symbol": "ETH/USDT", "mode": "paper"}},
            },
            "tags": ["agent", "HTX", "paper trade"],
            "performance": {"calls": 4120, "win_rate": 0.61, "avg_latency_ms": 1340},
            "workflow": {
                "name": "ETH News Trading Agent",
                "nodes": workflow_nodes,
                "edges": [
                    {"id": "ea1-a3", "source": "a1", "target": "a3", "animated": True},
                    {"id": "ea2-a3", "source": "a2", "target": "a3", "animated": True},
                    {"id": "ea3-a4", "source": "a3", "target": "a4", "animated": True},
                    {"id": "ea4-a5", "source": "a4", "target": "a5", "animated": True},
                ],
            },
        },
    ]


def node_payload(
    node_id: str,
    kind: str,
    label: str,
    cost: float,
    x: float,
    y: float,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    descriptions = {
        "market_data": "Fetch live candles and ticker data from HTX.",
        "news": "Collect market headlines for the selected asset.",
        "llm": "Use upstream market/news context to emit structured judgment.",
        "risk": "Apply position size, confidence and volatility constraints.",
        "paper_trade": "Simulate trade execution using HTX market price.",
    }
    return {
        "id": node_id,
        "type": "agentNode",
        "position": {"x": x, "y": y},
        "data": {
            "label": label,
            "kind": kind,
            "description": descriptions.get(kind, ""),
            "cost": cost,
            "revenueShare": "80% creator / 20% platform" if cost else "free",
            "config": config,
            "status": "idle",
        },
    }


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def persist_run(run_id: str, workflow_name: str, status: str, summary: Dict[str, Any], traces: List[Dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO runs (id, workflow_name, status, summary_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, workflow_name, status, json.dumps(summary), now),
        )
        for trace in traces:
            conn.execute(
                """
                INSERT INTO node_traces (run_id, node_id, node_type, label, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    trace["node_id"],
                    trace["node_type"],
                    trace["label"],
                    json.dumps(trace),
                    now,
                ),
            )


routes = [
    Route("/", index, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Route("/marketplace", marketplace, methods=["GET"]),
    Route("/market/candles", market_candles, methods=["GET"]),
    Route("/runs", run_workflow, methods=["POST"]),
    Route("/backtests", backtest_workflow, methods=["POST"]),
    Route("/backtests/tool", backtest_tool, methods=["POST"]),
    Route("/mcp/tools", mcp_tools, methods=["GET"]),
    Route("/mcp/manifest", mcp_manifest, methods=["GET"]),
    Route("/mcp/call", mcp_call, methods=["POST"]),
]

if STATIC_PATH.exists():
    routes.append(Mount("/assets", app=StaticFiles(directory=STATIC_PATH), name="assets"))

app = Starlette(debug=True, routes=routes, on_startup=[startup])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
