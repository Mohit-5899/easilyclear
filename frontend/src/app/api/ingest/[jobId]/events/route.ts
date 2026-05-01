/** Proxy: GET /api/ingest/{jobId}/events → FastAPI SSE. */

import { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  const upstream = await fetch(
    `${API_BASE_URL}/ingest/${encodeURIComponent(jobId)}/events`,
  );
  const headers = new Headers();
  headers.set("Content-Type", "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  return new Response(upstream.body, { status: upstream.status, headers });
}
