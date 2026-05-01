/** Proxy: POST /api/tests/{testId}/grade → FastAPI /tests/{testId}/grade. */

import { NextRequest } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ testId: string }> },
) {
  const { testId } = await params;
  const body = await req.text();
  const upstream = await fetch(
    `${API_BASE_URL}/tests/${encodeURIComponent(testId)}/grade`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
