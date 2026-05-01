/**
 * Mock test client + Zod schemas. Used by PracticeTab + /test/[id] pages.
 * Per spec docs/superpowers/specs/2026-05-03-mock-test.md.
 */

import { z } from "zod";

export const ChoiceSchema = z.enum(["A", "B", "C", "D"]);
export type Choice = z.infer<typeof ChoiceSchema>;

export const QuestionSchema = z.object({
  id: z.string(),
  prompt: z.string(),
  choices: z.object({
    A: z.string(),
    B: z.string(),
    C: z.string(),
    D: z.string(),
  }),
  correct: ChoiceSchema,
  answer_span: z.string(),
  source_node_id: z.string(),
  source_paragraph_ids: z.array(z.number()),
  difficulty: z.enum(["easy", "medium", "hard"]),
  bloom_level: z.enum(["remember", "understand", "apply", "analyze"]),
  // Backend may emit a partial record (one rationale per distractor).
  distractor_rationales: z.record(z.string(), z.string()).optional().default({}),
  explanation: z.string().default(""),
});
export type Question = z.infer<typeof QuestionSchema>;

export const MockTestSchema = z.object({
  test_id: z.string(),
  node_id: z.string(),
  book_slug: z.string().nullable(),
  questions: z.array(QuestionSchema),
  generated_at: z.string(),
  elapsed_seconds: z.number(),
});
export type MockTest = z.infer<typeof MockTestSchema>;

export const GradeDetailSchema = z.object({
  question_id: z.string(),
  user: ChoiceSchema.nullable(),
  correct: ChoiceSchema,
  is_correct: z.boolean(),
  explanation: z.string(),
});
export type GradeDetail = z.infer<typeof GradeDetailSchema>;

export const GradeResponseSchema = z.object({
  score: z.number(),
  total: z.number(),
  details: z.array(GradeDetailSchema),
});
export type GradeResponse = z.infer<typeof GradeResponseSchema>;

interface CreateTestParams {
  node_id: string;
  book_slug?: string;
  n?: number;
}

export async function createMockTest(params: CreateTestParams): Promise<MockTest> {
  const resp = await fetch("/api/tests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      node_id: params.node_id,
      book_slug: params.book_slug ?? null,
      n: params.n ?? 10,
    }),
  });
  if (!resp.ok) throw new Error(`createMockTest failed: ${resp.status}`);
  const data = await resp.json();
  return MockTestSchema.parse(data);
}

export async function getMockTest(testId: string): Promise<MockTest> {
  const resp = await fetch(`/api/tests/${encodeURIComponent(testId)}`);
  if (!resp.ok) throw new Error(`getMockTest failed: ${resp.status}`);
  return MockTestSchema.parse(await resp.json());
}

export async function gradeMockTest(
  testId: string,
  answers: Record<string, Choice>,
): Promise<GradeResponse> {
  const resp = await fetch(`/api/tests/${encodeURIComponent(testId)}/grade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!resp.ok) throw new Error(`gradeMockTest failed: ${resp.status}`);
  return GradeResponseSchema.parse(await resp.json());
}
