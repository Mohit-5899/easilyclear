# Tool Calling on Gemma 4 26B via OpenRouter

Date: 2026-05-01
Model: `google/gemma-4-26b-a4b-it` (paid tier)

## 1. Native Tool-Calling Support Status

OpenRouter's model card advertises "native function calling" and "structured output." The model appears in the `supported_parameters=tools` filter, so `tools` is accepted by the router. "Accepted" however does not equal "reliable." Reports (mlx-lm #1096, vLLM #38847, Ollama #15719) show Gemma 4's native markers (`<|tool_call>...{...}<tool_call|>`) frequently emit as plain text and fail to parse into OpenAI-compatible `tool_calls`. The `:free` tier is markedly worse — pydantic-ai #2976 sees `404 No endpoints support tool use` and `JSON mode not enabled`. Paid Gemma 4 26B is the better path, but still not parser-clean across every backend OpenRouter routes to.

## 2. Common Failure Modes

- Empty `tool_calls`, raw call text leaks into `content` (mlx-lm #1096).
- Provider-dependent: errors vary by routed backend (AI Studio vs Vertex vs DeepInfra).
- At 15+ tools, model falls back to ```json fenced output instead of tagged format.
- Infinite tool-call loops on Ollama 0.20.6+ via LiteLLM.
- No published BFCL score for Gemma 4 26B; Haiku and GPT-4o-mini have documented BFCL results and remain safer agentic baselines.

## 3. DECISION: Hybrid (native tools + prompt-JSON fallback)

Use native `tools` first on paid `google/gemma-4-26b-a4b-it`. If `tool_calls` is empty AND `content` matches a tool-call regex, parse content. If both fail, retry with `response_format: {type: "json_object"}` plus a system prompt asking for `{"action": "lookup_skill_content", "node_id": "...", "query": "..."}`. Protects the demo from parser regressions without abandoning structured output.

## 4. Code-Level Pattern Hint

```python
resp = client.chat.completions.create(
    model="google/gemma-4-26b-a4b-it",
    tools=[LOOKUP_SKILL_TOOL], tool_choice="auto",
    messages=msgs)
msg = resp.choices[0].message
call = msg.tool_calls[0] if msg.tool_calls else parse_inline_tool_call(msg.content)
if not call:
    call = json_mode_retry(client, msgs)  # response_format=json_object
```

Keep one `lookup_skill_content(node_id, query)` schema across all three paths so the executor is path-agnostic.
