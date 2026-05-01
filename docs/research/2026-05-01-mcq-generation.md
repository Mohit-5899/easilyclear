# MCQ Generation for RAS-Pre Tutor — Research Findings

Date: 2026-05-01 | Scope: prompt + schema for verifiable MCQs from source-preserved paragraphs.

## 1. Recommended Schema

```json
{
  "id": "uuid",
  "stem": "string (single, self-contained question)",
  "choices": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct": "A|B|C|D",
  "source_paragraph_ids": ["chunk_id_1", "..."],
  "answer_span": "verbatim substring from source supporting correct",
  "skill_node_id": "string (path in skill tree)",
  "difficulty": "easy|medium|hard",
  "bloom_level": "recall|understand|apply|analyze",
  "explanation": "1-2 sentences citing source",
  "distractor_rationales": {"A": "why wrong", "...": "..."}
}
```
Additions to your draft: `answer_span` (enables span verification), `bloom_level` (orthogonal to difficulty), `distractor_rationales` (forces model to justify each wrong option, surfaces ambiguity).

## 2. Prompt Template Skeleton

```
SYSTEM: You write RAS-Pre MCQs. Use ONLY the SOURCE. If a fact is not present verbatim, do not use it.
USER:
SOURCE (verbatim, do not paraphrase facts):
<<<{paragraph_text}>>>
SKILL: {node_path}    DIFFICULTY: {easy|medium|hard}
TASK:
1. Pick ONE atomic fact from SOURCE.
2. Write a stem testing that fact (no "all of the above").
3. Set `answer_span` = exact substring of SOURCE supporting the answer.
4. Generate 3 distractors that are: same category as answer, plausible to a novice, unambiguously contradicted by SOURCE. Provide a rationale per distractor.
5. Output strict JSON matching SCHEMA. No prose.
SELF-CHECK before emitting: (a) answer_span ⊂ SOURCE, (b) only ONE choice is supported by SOURCE, (c) distractors are not synonyms of correct.
```

## 3. Validation Strategy (layered, cheap → expensive)

1. **Schema/JSON parse** — reject malformed.
2. **Span check** — `answer_span` must be exact substring of cited paragraphs (string match).
3. **Single-correct check** — re-prompt judge LLM with SOURCE + choices, must return same letter; flag if disagree.
4. **Distractor-falsifiability check** — judge LLM asserts each distractor is contradicted/unsupported by SOURCE.
5. **Closed-book leakage probe** — ask generator (no SOURCE) to answer; if accuracy >70% the question is trivia/memorizable, not source-grounded — drop or mark low-value (MMLU-Pro pattern).
6. **Human spot-review** — sample 5% per skill node.

## 4. DECISION

Adopt **schema-constrained generation + 3-stage automatic validation (span match → LLM-judge single-correct → leakage probe)**, mirroring MMLU-Pro's "GPT-4 generate + expert vet" but replacing expert review with deterministic span verification (cheap, hackathon-friendly) plus one LLM-judge pass. Difficulty is set by `bloom_level` + distractor semantic distance (easy = lexical foils, hard = same-category near-miss numbers/dates/named-entities, multi-hop within paragraph).

## 5. Pitfalls to Avoid

- **Hallucinated facts**: never let the model invent numbers/dates not in the span — enforce `answer_span ⊂ source`.
- **Textual shortcuts**: distractors with different length/style than correct leak the answer (VLM-MCQ bias finding).
- **Synonym distractors**: two choices semantically equivalent → ambiguous; reject via judge.
- **"All/none of the above"** and negation stems — high error rate, banned in MMLU-Pro.
- **Difficulty inflation by obscurity**: hard ≠ trivia. Keep hard = reasoning depth (multi-fact, application), not rare-fact recall.

## Sources

- MMLU-Pro paper (arXiv 2406.01574) — 10-option, GPT-4 + expert vet pipeline.
- "Concept Map-Based MCQ Generation" (arXiv 2505.02850) — structured-knowledge distractors.
- "LookAlike: Consistent Distractor Generation" (arXiv 2505.01903).
- "Distractor Generation with Predictive Prompting" (arXiv 2307.16338).
- OpenAI Evals docs — basic vs model-graded templates; CoT-before-score.
- RAGAS / "Correctness ≠ Faithfulness in RAG Attributions" (SIGIR-ICTIR 2025) — span-grounding over post-rationalization.
