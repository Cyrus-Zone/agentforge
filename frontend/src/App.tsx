import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type EdgeChange,
  Handle,
  Position,
} from "reactflow";
import {
  Activity,
  Bot,
  Boxes,
  BrainCircuit,
  CircleDollarSign,
  DatabaseZap,
  FileClock,
  Gauge,
  Globe2,
  Network,
  Newspaper,
  Play,
  Plus,
  Route,
  ShieldCheck,
  Store,
  Wand2,
} from "lucide-react";
import { api } from "./api";
import type { AppNodeData, MarketplaceItem, NodeKind, NodeTrace, RunResult } from "./types";

const nodeCatalog: Array<{
  kind: NodeKind;
  label: string;
  description: string;
  cost: number;
  icon: typeof Activity;
  config: AppNodeData["config"];
}> = [
  {
    kind: "market_data",
    label: "HTX Market Data",
    description: "Fetch live candles and ticker data from HTX.",
    cost: 0,
    icon: DatabaseZap,
    config: { symbol: "ethusdt", timeframe: "60min", candles: 100 },
  },
  {
    kind: "news",
    label: "News Tool",
    description: "Collect market headlines for the selected asset.",
    cost: 0.001,
    icon: Newspaper,
    config: { topic: "ETH ETF crypto market", limit: 5 },
  },
  {
    kind: "llm",
    label: "LLM Analysis",
    description: "Use upstream market/news context to emit structured judgment.",
    cost: 0.006,
    icon: BrainCircuit,
    config: {
      model: "demo-llm",
      prompt:
        "Given market_data and news, return JSON with trend, confidence, reason, suggested_action, risk_flags.",
    },
  },
  {
    kind: "sentiment_tool",
    label: "Sentiment Tool",
    description: "Reusable marketplace tool that scores market sentiment.",
    cost: 0.004,
    icon: Wand2,
    config: { source: "marketplace:eth-sentiment-lab", output_schema: "sentiment,confidence,drivers" },
  },
  {
    kind: "risk",
    label: "Risk Check",
    description: "Apply position size, confidence and volatility constraints.",
    cost: 0.002,
    icon: ShieldCheck,
    config: { max_position_pct: 20, stop_loss_pct: 3, min_confidence: 0.62 },
  },
  {
    kind: "paper_trade",
    label: "HTX Paper Trade",
    description: "Simulate trade execution using HTX market price.",
    cost: 0.001,
    icon: Route,
    config: { quote_size_usdt: 1000, mode: "paper", exchange: "HTX" },
  },
  {
    kind: "condition",
    label: "Condition",
    description: "Branch on structured fields such as confidence or action.",
    cost: 0,
    icon: Gauge,
    config: { expression: "confidence > 0.62 && suggested_action == buy" },
  },
  {
    kind: "end",
    label: "End",
    description: "Terminal output node for final agent result.",
    cost: 0,
    icon: FileClock,
    config: { summarize: true },
  },
];

const initialNodes: Node<AppNodeData>[] = [
  makeNode("n1", "market_data", { x: 80, y: 130 }),
  makeNode("n2", "news", { x: 360, y: 70 }),
  makeNode("n3", "llm", { x: 640, y: 130 }),
  makeNode("n4", "risk", { x: 920, y: 130 }),
  makeNode("n5", "paper_trade", { x: 1200, y: 130 }),
];

const initialEdges: Edge[] = [
  { id: "e1-3", source: "n1", target: "n3", animated: true },
  { id: "e2-3", source: "n2", target: "n3", animated: true },
  { id: "e3-4", source: "n3", target: "n4", animated: true },
  { id: "e4-5", source: "n4", target: "n5", animated: true },
];

function makeNode(id: string, kind: NodeKind, position: { x: number; y: number }): Node<AppNodeData> {
  const template = nodeCatalog.find((node) => node.kind === kind)!;
  return {
    id,
    type: "agentNode",
    position,
    data: {
      label: template.label,
      kind,
      description: template.description,
      cost: template.cost,
      revenueShare: template.cost > 0 ? "80% creator / 20% platform" : "free",
      config: { ...template.config },
      status: "idle",
    },
  };
}

function AgentNode({ data }: { data: AppNodeData }) {
  const Icon = nodeCatalog.find((node) => node.kind === data.kind)?.icon ?? Activity;
  return (
    <div className={`agent-node ${data.status ?? "idle"}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-topline">
        <span className="node-icon">
          <Icon size={16} />
        </span>
        <span className="node-kind">{data.kind.replace("_", " ")}</span>
      </div>
      <div className="node-title">{data.label}</div>
      <div className="node-description">{data.description}</div>
      <div className="node-meta">
        <span>${data.cost.toFixed(3)} / call</span>
        <span>{data.status ?? "idle"}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

export function App() {
  const [nodes, setNodes] = useState<Node<AppNodeData>[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("n3");
  const [marketplace, setMarketplace] = useState<MarketplaceItem[]>([]);
  const [mcpTools, setMcpTools] = useState<Array<{ name: string; description: string }>>([]);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [activePanel, setActivePanel] = useState<"trace" | "marketplace" | "mcp">("trace");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.marketplace().then(setMarketplace).catch(() => setMarketplace([]));
    api.mcpTools()
      .then((result) => setMcpTools(result.tools))
      .catch(() => setMcpTools([]));
  }, []);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((current) => applyNodeChanges(changes, current)),
    [],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((current) => applyEdgeChanges(changes, current)),
    [],
  );

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((current) => addEdge({ ...connection, animated: true }, current)),
    [],
  );

  const addNode = (kind: NodeKind) => {
    const id = `n${Date.now()}`;
    const next = makeNode(id, kind, {
      x: 160 + Math.random() * 520,
      y: 120 + Math.random() * 320,
    });
    setNodes((current) => [...current, next]);
    setSelectedNodeId(id);
  };

  const updateSelectedConfig = (key: string, value: string) => {
    if (!selectedNode) return;
    setNodes((current) =>
      current.map((node) =>
        node.id === selectedNode.id
          ? {
              ...node,
              data: {
                ...node.data,
                config: { ...node.data.config, [key]: coerceValue(value) },
              },
            }
          : node,
      ),
    );
  };

  const run = async (mode: "run" | "backtest") => {
    setIsRunning(true);
    setError(null);
    setRunResult(null);
    setActivePanel("trace");
    setNodes((current) => current.map((node) => ({ ...node, data: { ...node.data, status: "idle" } })));
    try {
      const workflow = { name: "ETH News Trading Agent", nodes, edges };
      const result = mode === "run" ? await api.runWorkflow(workflow) : await api.backtest(workflow);
      setRunResult(result);
      const successful = new Set(result.traces.map((trace) => trace.node_id));
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          data: { ...node.data, status: successful.has(node.id) ? "success" : "idle" },
        })),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run failed");
    } finally {
      setIsRunning(false);
    }
  };

  const importMarketplaceItem = (item: MarketplaceItem) => {
    if (item.workflow?.nodes?.length) {
      setNodes(item.workflow.nodes);
      setEdges(item.workflow.edges);
      setSelectedNodeId(item.workflow.nodes[0]?.id ?? null);
      setActivePanel("trace");
      return;
    }

    const id = `m${Date.now()}`;
    setNodes((current) => [
      ...current,
      {
        id,
        type: "agentNode",
        position: { x: 420 + Math.random() * 380, y: 180 + Math.random() * 260 },
        data: {
          label: item.name,
          kind: (item.nodeTemplate?.kind as NodeKind) ?? "sentiment_tool",
          description: item.subtitle,
          cost: item.price_usd,
          revenueShare: "80% creator / 20% platform",
          config: item.nodeTemplate?.config ?? { marketplace_id: item.id },
          status: "idle",
        },
      },
    ]);
    setSelectedNodeId(id);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Network size={19} />
          </div>
          <div>
            <strong>AgentForge</strong>
            <span>From visual strategy to executable agent</span>
          </div>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" onClick={() => setActivePanel("marketplace")}>
            <Store size={16} />
            Marketplace
          </button>
          <button className="ghost-button" onClick={() => setActivePanel("mcp")}>
            <Boxes size={16} />
            MCP
          </button>
          <button className="secondary-button" onClick={() => run("backtest")} disabled={isRunning}>
            <FileClock size={16} />
            Backtest
          </button>
          <button className="primary-button" onClick={() => run("run")} disabled={isRunning}>
            <Play size={16} />
            {isRunning ? "Running" : "Run Agent"}
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="node-palette">
          <div className="panel-heading">
            <span>Node Library</span>
            <small>Composable trading blocks</small>
          </div>
          <div className="node-list">
            {nodeCatalog.map((item) => {
              const Icon = item.icon;
              return (
                <button key={item.kind} className="palette-item" onClick={() => addNode(item.kind)}>
                  <span className="palette-icon">
                    <Icon size={17} />
                  </span>
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                  <Plus size={15} />
                </button>
              );
            })}
          </div>
        </aside>

        <section className="flow-board">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
          >
            <Background color="#d4dbe8" gap={18} />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>
        </section>

        <aside className="config-panel">
          <div className="panel-heading">
            <span>Configuration</span>
            <small>Selected node</small>
          </div>
          {selectedNode ? (
            <div className="config-body">
              <div className="config-card">
                <div className="config-title">
                  <Bot size={18} />
                  <strong>{selectedNode.data.label}</strong>
                </div>
                <p>{selectedNode.data.description}</p>
                <div className="cost-line">
                  <CircleDollarSign size={16} />
                  <span>${selectedNode.data.cost.toFixed(3)} per call</span>
                </div>
                <div className="share-line">{selectedNode.data.revenueShare}</div>
              </div>
              <div className="fields">
                {Object.entries(selectedNode.data.config).map(([key, value]) => (
                  <label key={key}>
                    <span>{key}</span>
                    <input value={String(value)} onChange={(event) => updateSelectedConfig(key, event.target.value)} />
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state">Select a node to edit inputs, prompt, cost, and schema.</div>
          )}
        </aside>
      </main>

      <section className="bottom-panel">
        <div className="tabs">
          <button className={activePanel === "trace" ? "active" : ""} onClick={() => setActivePanel("trace")}>
            Trace
          </button>
          <button
            className={activePanel === "marketplace" ? "active" : ""}
            onClick={() => setActivePanel("marketplace")}
          >
            Marketplace
          </button>
          <button className={activePanel === "mcp" ? "active" : ""} onClick={() => setActivePanel("mcp")}>
            MCP Tools
          </button>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {activePanel === "trace" ? <TracePanel result={runResult} /> : null}
        {activePanel === "marketplace" ? (
          <MarketplacePanel items={marketplace} onImport={importMarketplaceItem} />
        ) : null}
        {activePanel === "mcp" ? <McpPanel tools={mcpTools} /> : null}
      </section>
    </div>
  );
}

function TracePanel({ result }: { result: RunResult | null }) {
  if (!result) {
    return (
      <div className="empty-state">
        Run the agent to see every node input, output, latency, cost, and creator split.
      </div>
    );
  }

  return (
    <div className="trace-layout">
      <div className="run-summary">
        <div>
          <small>Run</small>
          <strong>{result.run_id}</strong>
        </div>
        <div>
          <small>Status</small>
          <strong>{result.status}</strong>
        </div>
        <div>
          <small>Total cost</small>
          <strong>${Number(result.summary.total_cost_usd ?? 0).toFixed(3)}</strong>
        </div>
        <div>
          <small>Decision</small>
          <strong>{String(result.summary.final_action ?? result.summary.mode ?? "ready")}</strong>
        </div>
      </div>
      <div className="trace-list">
        {result.traces.map((trace, index) => (
          <TraceCard key={`${trace.node_id}-${index}`} trace={trace} index={index + 1} />
        ))}
      </div>
    </div>
  );
}

function TraceCard({ trace, index }: { trace: NodeTrace; index: number }) {
  return (
    <article className="trace-card">
      <div className="trace-header">
        <span>{index}</span>
        <div>
          <strong>{trace.label}</strong>
          <small>{trace.node_type}</small>
        </div>
        <em>{trace.duration_ms}ms</em>
      </div>
      <div className="trace-grid">
        <pre>{JSON.stringify(trace.input, null, 2)}</pre>
        <pre>{JSON.stringify(trace.output, null, 2)}</pre>
      </div>
      <div className="trace-footer">
        <span>Cost ${trace.cost_usd.toFixed(3)}</span>
        <span>
          Creator ${Number(trace.revenue_split.creator ?? 0).toFixed(3)} / Platform $
          {Number(trace.revenue_split.platform ?? 0).toFixed(3)}
        </span>
      </div>
    </article>
  );
}

function MarketplacePanel({
  items,
  onImport,
}: {
  items: MarketplaceItem[];
  onImport: (item: MarketplaceItem) => void;
}) {
  return (
    <div className="marketplace-grid">
      {items.map((item) => (
        <article className="market-card" key={item.id}>
          <div className="market-top">
            <span>{item.type}</span>
            <strong>${item.price_usd.toFixed(3)} / call</strong>
          </div>
          <h3>{item.name}</h3>
          <p>{item.description}</p>
          <div className="tag-row">
            {item.tags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
          <div className="market-stats">
            <span>{item.performance.calls.toLocaleString()} calls</span>
            <span>{item.performance.avg_latency_ms}ms avg</span>
            {item.performance.win_rate ? <span>{Math.round(item.performance.win_rate * 100)}% win</span> : null}
          </div>
          <button className="secondary-button" onClick={() => onImport(item)}>
            <Plus size={15} />
            Import to canvas
          </button>
        </article>
      ))}
    </div>
  );
}

function McpPanel({ tools }: { tools: Array<{ name: string; description: string }> }) {
  return (
    <div className="mcp-panel">
      <div className="mcp-copy">
        <Globe2 size={20} />
        <div>
          <strong>Marketplace tools and agents become callable infrastructure.</strong>
          <p>
            External MCP clients can list tools, call a published tool, or run a published trading agent with
            structured inputs.
          </p>
        </div>
      </div>
      <div className="mcp-tools">
        {tools.map((tool) => (
          <div key={tool.name}>
            <strong>{tool.name}</strong>
            <span>{tool.description}</span>
          </div>
        ))}
      </div>
      <pre>{`POST /mcp/call
{
  "tool": "call_marketplace_tool",
  "arguments": {
    "tool_id": "eth-sentiment-lab",
    "input": { "symbol": "ETH/USDT" }
  }
}`}</pre>
    </div>
  );
}

function coerceValue(value: string) {
  if (value === "true") return true;
  if (value === "false") return false;
  const numeric = Number(value);
  return Number.isNaN(numeric) || value.trim() === "" ? value : numeric;
}
