import type { Edge, Node } from "reactflow";

export type NodeKind =
  | "market_data"
  | "news"
  | "llm"
  | "sentiment_tool"
  | "risk"
  | "paper_trade"
  | "condition"
  | "end";

export type AppNodeData = {
  label: string;
  kind: NodeKind;
  description: string;
  cost: number;
  revenueShare?: string;
  config: Record<string, string | number | boolean>;
  status?: "idle" | "running" | "success" | "error";
};

export type WorkflowPayload = {
  name: string;
  nodes: Node<AppNodeData>[];
  edges: Edge[];
};

export type NodeTrace = {
  node_id: string;
  node_type: NodeKind;
  label: string;
  status: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  cost_usd: number;
  revenue_split: Record<string, number>;
  duration_ms: number;
  started_at: string;
};

export type RunResult = {
  run_id: string;
  workflow_name: string;
  status: string;
  summary: Record<string, unknown>;
  traces: NodeTrace[];
};

export type MarketplaceItem = {
  id: string;
  type: "tool" | "agent";
  name: string;
  subtitle: string;
  description: string;
  author: string;
  price_usd: number;
  tags: string[];
  performance: {
    calls: number;
    win_rate?: number;
    avg_latency_ms: number;
  };
  workflow?: WorkflowPayload;
  nodeTemplate?: Partial<AppNodeData>;
};
