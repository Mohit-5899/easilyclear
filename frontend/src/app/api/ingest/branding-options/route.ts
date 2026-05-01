/** Proxy: GET /api/ingest/branding-options → FastAPI /ingest/branding-options. */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const upstream = await fetch(`${API_BASE_URL}/ingest/branding-options`);
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
