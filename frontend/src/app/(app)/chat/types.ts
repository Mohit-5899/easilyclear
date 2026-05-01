/**
 * Shared types for the agentic chat page. The backend emits AI SDK UI
 * Message Stream events with two extras for tool-calling (per
 * docs/research/2026-05-02-ux-redesign-architecture.md §3 streaming UX).
 */

export type Scope = "all" | "book" | "node";

export interface Citation {
  index: number;
  node_id: string;
  paragraph_id: number;
  page: number;
  snippet: string;
}

export interface ToolCallEvent {
  id: string;
  query: string;
  scope: Scope;
  bookSlug?: string;
  nodeId?: string;
  hitCount?: number; // filled when tool-result arrives
  scopeLabel?: string;
}

export interface AssistantTurn {
  role: "assistant";
  text: string;
  toolCalls: ToolCallEvent[];
  citations: Citation[];
  status: "streaming" | "complete" | "error";
}

export interface UserTurn {
  role: "user";
  text: string;
}

export type ChatTurn = UserTurn | AssistantTurn;
