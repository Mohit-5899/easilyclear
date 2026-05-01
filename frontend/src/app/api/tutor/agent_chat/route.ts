/** Proxy: POST /api/tutor/agent_chat → FastAPI /tutor/agent_chat (SSE). */

import { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${API_BASE_URL}/tutor/agent_chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });

  const headers = new Headers();
  headers.set("Content-Type", "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  const proto = upstream.headers.get("x-vercel-ai-ui-message-stream");
  if (proto) headers.set("x-vercel-ai-ui-message-stream", proto);

  return new Response(upstream.body, { status: upstream.status, headers });
}
