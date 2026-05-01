/**
 * Tutor chat proxy — forwards POST /api/tutor/chat to FastAPI's /tutor/chat
 * preserving the SSE stream and the AI SDK UI Message Stream protocol header.
 *
 * Per spec docs/superpowers/specs/2026-05-02-tutor-chat.md and research note
 * docs/research/2026-05-01-streaming-chat.md — the FastAPI backend emits the
 * AI SDK protocol directly, so this route just proxies the body and headers.
 */

import { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.text();

  const upstream = await fetch(`${API_BASE_URL}/tutor/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body,
  });

  // Forward the upstream stream + protocol header.
  const headers = new Headers();
  headers.set("Content-Type", "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  const proto = upstream.headers.get("x-vercel-ai-ui-message-stream");
  if (proto) headers.set("x-vercel-ai-ui-message-stream", proto);

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
