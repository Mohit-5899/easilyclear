"use client";

import { useCallback, useRef, useState } from "react";

import type {
  AssistantTurn,
  ChatTurn,
  Citation,
  Scope,
  ToolCallEvent,
} from "../types";

/**
 * useAgentStream — the SSE state machine for /chat.
 *
 * Owns the fetch + AI SDK UI Message Stream parser + per-event mutators
 * that append tool calls / citations / text deltas to the last assistant
 * turn. Returns a controlled `turns` value that the parent renders.
 *
 * Side effects (abort controller, streaming flag) stay inside this hook;
 * the page just renders state and forwards user actions.
 */
export function useAgentStream(initialTurns: ChatTurn[] = []) {
  const [turns, setTurns] = useState<ChatTurn[]>(initialTurns);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback((next: ChatTurn[] = []) => {
    setTurns(next);
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const send = useCallback(
    async (text: string, scope: Scope) => {
      if (!text.trim() || streaming) return;
      setStreaming(true);

      const userTurn: ChatTurn = { role: "user", text };
      const assistantSeed: AssistantTurn = {
        role: "assistant",
        text: "",
        toolCalls: [],
        citations: [],
        status: "streaming",
      };
      const newTurns: ChatTurn[] = [...turns, userTurn, assistantSeed];
      setTurns(newTurns);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const resp = await fetch("/api/tutor/agent_chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: newTurns
              .filter(
                (t): t is ChatTurn => t.role !== "assistant" || t.text.length > 0,
              )
              .map((t) =>
                t.role === "user"
                  ? { role: "user", content: t.text }
                  : { role: "assistant", content: (t as AssistantTurn).text },
              )
              .concat([{ role: "user", content: text }]),
            default_scope: scope,
            max_steps: 3,
          }),
          signal: controller.signal,
        });

        if (!resp.ok || !resp.body) {
          throw new Error(`agent_chat failed: ${resp.status}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            if (!frame.startsWith("data: ")) continue;
            const payload = frame.slice(6).trim();
            if (!payload || payload === "[DONE]") continue;
            try {
              applyEvent(JSON.parse(payload), setTurns);
            } catch {
              // ignore malformed frames
            }
          }
        }

        setTurns((prev) =>
          prev.map((t, i) =>
            i === prev.length - 1 && t.role === "assistant"
              ? { ...t, status: "complete" }
              : t,
          ),
        );
      } catch (err) {
        const aborted = (err as Error).name === "AbortError";
        if (!aborted) {
          setTurns((prev) =>
            prev.map((t, i) => {
              if (i !== prev.length - 1 || t.role !== "assistant") return t;
              return {
                ...t,
                text: t.text || `[error: ${(err as Error).message}]`,
                status: "error",
              };
            }),
          );
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [streaming, turns],
  );

  return { turns, streaming, send, stop, reset, setTurns };
}

/**
 * Fold one SSE event into the turn list. Only the LAST assistant turn is
 * mutated — earlier turns are immutable history.
 */
function applyEvent(
  ev: Record<string, unknown>,
  setTurns: React.Dispatch<React.SetStateAction<ChatTurn[]>>,
) {
  const t = String(ev.type ?? "");
  if (t === "tool-call") {
    const args = (ev.args as Record<string, unknown>) ?? {};
    const call: ToolCallEvent = {
      id: String(ev.id ?? ""),
      query: String(args.query ?? ""),
      scope: (args.scope as Scope) ?? "all",
      subjectSlug: (args.subject_slug ?? args.book_slug ?? undefined) as
        | string
        | undefined,
      nodeId: (args.node_id ?? undefined) as string | undefined,
    };
    setTurns((prev) => mutateLastAssistant(prev, (a) => ({
      ...a,
      toolCalls: [...a.toolCalls, call],
    })));
  } else if (t === "tool-result") {
    const id = String(ev.id ?? "");
    const patch = {
      hitCount: Number(ev.hit_count ?? 0),
      scopeLabel: String(ev.scope_label ?? ""),
    };
    setTurns((prev) => mutateLastAssistant(prev, (a) => ({
      ...a,
      toolCalls: a.toolCalls.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    })));
  } else if (t === "data-citation") {
    const data = ev.data as Citation;
    setTurns((prev) => mutateLastAssistant(prev, (a) => ({
      ...a,
      citations: [...a.citations, data],
    })));
  } else if (t === "text-delta") {
    const delta = String((ev as { delta?: string }).delta ?? "");
    setTurns((prev) => mutateLastAssistant(prev, (a) => ({
      ...a,
      text: a.text + delta,
    })));
  }
}

function mutateLastAssistant(
  turns: ChatTurn[],
  fn: (t: AssistantTurn) => AssistantTurn,
): ChatTurn[] {
  return turns.map((t, i) => {
    if (i !== turns.length - 1 || t.role !== "assistant") return t;
    return fn(t);
  });
}
