/** Proxy: POST /api/ingest → FastAPI /ingest (multipart). */

import { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  // Forward multipart form-data unchanged.
  const upstream = await fetch(`${API_BASE_URL}/ingest`, {
    method: "POST",
    headers: { "content-type": req.headers.get("content-type") ?? "" },
    body: req.body,
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
