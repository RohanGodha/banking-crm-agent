# Execution flow — per-query timeline

This document complements the README §3 with a more granular timeline of a single RM query and the latency budget we target.

## Sequence

```
t = 0 ms        UI sends POST /chat/stream  { rm_query }
t ≈ 30 ms       Auth middleware verifies X-Access-Token (constant-time compare)
                Backend opens SSE response, emits {event: info, session_id}

t ≈ 60–900 ms   Planner node
                  ├─ load planner_system.md
                  ├─ LLMRouter.complete(kind=reasoning, json_mode=True)
                  │     → Gemini 2.0 Flash, ~800 ms typical P50
                  ├─ Pydantic-validate the plan JSON
                  └─ emit {event: plan, plan, intent, target_product, latency_ms, llm_route}

t ≈ 900–1500 ms Step 1: query_customers
                  ├─ FailoverSource → DatabricksSource (5s timeout) OR SQLite
                  ├─ Returns up to 80 customer rows
                  ├─ emit {event: tool_call} then {event: tool_result, source, rows, latency_ms}
                  └─ Critic → pass → cursor advances

t ≈ 1500–2200ms Step 2: compute_customer_value
                  ├─ asyncio.gather over N customers: profile + txns + value scoring
                  ├─ Returns sorted by value_score desc
                  └─ Trace event + Critic → pass

t ≈ 2200–2900ms Step 3: predict_loan_propensity
                  ├─ asyncio.gather per customer: profile + txns + holdings + interactions
                  ├─ Weighted logistic with product-specific features
                  └─ Trace event + Critic → pass

t ≈ 2900–3300ms Step 4: recommend_products
                  ├─ Eligibility check + per-product propensity rerun
                  └─ Trace event + Critic → pass

t ≈ 3300–3700ms Step 5: search_interactions  (hybrid RAG)
                  ├─ Gemini embed(query)
                  ├─ Chroma similarity (cosine) + BM25 lexical
                  ├─ Reciprocal Rank Fusion
                  ├─ MMR re-rank (λ=0.7)
                  └─ Returns top-k cited snippets

t ≈ 3700–4400ms Synthesizer
                  ├─ Build CandidateRecord list (merge value + propensity + recommendation + citations)
                  ├─ Emit one {event: candidate} per CandidateRecord (UI paints rows live)
                  ├─ Gemini summary (≤120 words) → {event: synth, summary}
                  └─ The user-visible "assistant" bubble streams in

t ≈ 4400–6500ms MessageGenerator (parallel, N candidates)
                  ├─ asyncio.gather → Groq Llama 3.3, ~0.5 s per draft
                  ├─ compliance_check strips ungrounded numbers
                  └─ Emit {event: draft} per candidate

t ≈ 6500–6700ms Responder
                  ├─ INSERT OR IGNORE session row
                  ├─ Persist drafts via create_outreach_batch tool
                  ├─ Persist agent_traces rows for replay
                  └─ Emit {event: final, summary, candidates, drafts}

t ≈ 6700 ms     UI closes SSE; RM clicks a candidate to open the drawer.
```

## Latency budget targets

| Stage                                | Target P50 | Target P95 | Optimisations applied |
| ------------------------------------ | ---------: | ---------: | --------------------- |
| Auth + session init                  |     30 ms  |     80 ms  | in-memory hmac compare, INSERT-OR-IGNORE |
| Planner (Gemini, JSON mode)          |    800 ms  |  1,500 ms  | terse system prompt, no fewshot bloat    |
| Tool steps (5, mostly parallel inside) |   1,200 ms |  2,500 ms  | asyncio.gather, SQLite WAL, embedding cache |
| Critic (×5)                          |    100 ms  |    300 ms  | rule-based with optional LLM upgrade     |
| Synthesizer (Gemini)                 |    700 ms  |  1,400 ms  | streamed                                 |
| MessageGen × 10 (parallel via Groq)  |  1,200 ms  |  2,500 ms  | Groq's sub-second + asyncio fanout       |
| Responder + persistence              |    150 ms  |    400 ms  | single SQLite connection                 |
| **End-to-end**                       | **~4 s**   | **~7 s**   |                                          |
| **Perceived first event**            | **<1 s**   | **<1.5 s** | SSE: plan streams before any tool call   |

## Why these latencies are achievable on Render free tier

- Parallel asyncio fanout cuts per-customer tool calls from O(N) to O(1) in wall time.
- Embedding cache (Chroma is persistent on disk) means we never re-embed at query time.
- The Groq free tier returns ~0.5 s per generation; 10 in parallel is ~1.2 s wall time.
- Gemini's `gemini-2.0-flash-exp` is the fastest free Gemini model with reliable JSON-mode adherence.
- Render's `512 MB` RAM is enough because we never load a torch model — scoring is pure numpy.
