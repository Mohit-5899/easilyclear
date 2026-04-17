"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type HealthResponse, type LLMTestResponse } from "@/lib/api";

type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };

export default function Home() {
  const [health, setHealth] = useState<AsyncState<HealthResponse>>({
    status: "idle",
  });
  const [prompt, setPrompt] = useState("Say hi in one short sentence.");
  const [llm, setLlm] = useState<AsyncState<LLMTestResponse>>({ status: "idle" });

  const loadHealth = useCallback(async () => {
    setHealth({ status: "loading" });
    try {
      const data = await api.health();
      setHealth({ status: "success", data });
    } catch (err) {
      setHealth({ status: "error", error: (err as Error).message });
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  const sendPrompt = useCallback(async () => {
    setLlm({ status: "loading" });
    try {
      const data = await api.llmTest(prompt);
      setLlm({ status: "success", data });
    } catch (err) {
      setLlm({ status: "error", error: (err as Error).message });
    }
  }, [prompt]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <div className="max-w-3xl mx-auto space-y-8">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">Gemma Tutor</h1>
          <p className="text-slate-400 mt-1">
            Day 1 scaffold — backend + LLM abstraction verified
          </p>
        </header>

        <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Backend health</h2>
            <button
              onClick={loadHealth}
              className="text-xs px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 transition"
            >
              Refresh
            </button>
          </div>
          <div className="mt-4 font-mono text-sm">
            {health.status === "loading" && (
              <p className="text-slate-400">Checking…</p>
            )}
            {health.status === "error" && (
              <p className="text-red-400">Error: {health.error}</p>
            )}
            {health.status === "success" && (
              <div className="space-y-1 text-slate-300">
                <p>
                  <span className="text-slate-500">ok:</span>{" "}
                  <span className="text-emerald-400">
                    {String(health.data.ok)}
                  </span>
                </p>
                <p>
                  <span className="text-slate-500">app:</span> {health.data.app}
                </p>
                <p>
                  <span className="text-slate-500">env:</span> {health.data.env}
                </p>
                <p>
                  <span className="text-slate-500">llm_provider:</span>{" "}
                  <span className="text-sky-400">{health.data.llm_provider}</span>
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-5">
          <h2 className="text-lg font-medium">LLM round-trip test</h2>
          <p className="text-sm text-slate-500 mt-1">
            Calls <code className="text-slate-400">POST /llm/test</code> on the
            backend, which routes through the{" "}
            <code className="text-slate-400">LLMClient</code> protocol to the
            currently selected provider.
          </p>

          <div className="mt-4 space-y-3">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-sky-500"
            />
            <button
              onClick={sendPrompt}
              disabled={llm.status === "loading"}
              className="px-4 py-2 text-sm rounded bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:cursor-not-allowed transition"
            >
              {llm.status === "loading" ? "Thinking…" : "Send to LLM"}
            </button>
          </div>

          {llm.status === "error" && (
            <p className="mt-4 text-red-400 text-sm font-mono">
              Error: {llm.error}
            </p>
          )}
          {llm.status === "success" && (
            <div className="mt-4 rounded border border-slate-800 bg-slate-950 p-4 space-y-2">
              <div className="flex gap-4 text-xs text-slate-500 flex-wrap">
                <span>
                  provider:{" "}
                  <span className="text-sky-400">{llm.data.provider}</span>
                </span>
                <span>
                  model: <span className="text-slate-300">{llm.data.model}</span>
                </span>
                {llm.data.prompt_tokens != null && (
                  <span>tokens in: {llm.data.prompt_tokens}</span>
                )}
                {llm.data.completion_tokens != null && (
                  <span>tokens out: {llm.data.completion_tokens}</span>
                )}
              </div>
              <p className="font-mono text-sm whitespace-pre-wrap text-slate-200">
                {llm.data.content}
              </p>
            </div>
          )}
        </section>

        <footer className="text-xs text-slate-600 pt-4">
          Swap providers: edit <code>backend/.env</code> →{" "}
          <code>LLM_PROVIDER=mock|openrouter|ollama</code>
        </footer>
      </div>
    </main>
  );
}
