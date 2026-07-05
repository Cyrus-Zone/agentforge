import type { MarketplaceItem, RunResult, WorkflowPayload } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  marketplace: () => request<MarketplaceItem[]>("/marketplace"),
  runWorkflow: (workflow: WorkflowPayload) =>
    request<RunResult>("/runs", {
      method: "POST",
      body: JSON.stringify(workflow),
    }),
  backtest: (workflow: WorkflowPayload) =>
    request<RunResult>("/backtests", {
      method: "POST",
      body: JSON.stringify(workflow),
    }),
  mcpTools: () =>
    request<{
      tools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>;
    }>("/mcp/tools"),
};
