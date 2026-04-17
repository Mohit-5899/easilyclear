import { z } from "zod";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

export const HealthResponseSchema = z.object({
  ok: z.boolean(),
  app: z.string(),
  env: z.string(),
  llm_provider: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const LLMTestResponseSchema = z.object({
  provider: z.string(),
  model: z.string(),
  content: z.string(),
  prompt_tokens: z.number().nullable(),
  completion_tokens: z.number().nullable(),
});
export type LLMTestResponse = z.infer<typeof LLMTestResponseSchema>;

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (err) {
    throw new Error(
      `Network error hitting ${path} — is the backend running on ${API_BASE_URL}?`,
    );
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }

  const json = await res.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    throw new Error(
      `Response from ${path} did not match schema: ${parsed.error.message}`,
    );
  }
  return parsed.data;
}

export const api = {
  health: () => request("/health", HealthResponseSchema),
  llmTest: (prompt: string) =>
    request("/llm/test", LLMTestResponseSchema, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
};
