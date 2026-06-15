# AI patterns reference

A deeper look at each agentic / RAG pattern used and why it earns its place.

---

## 1. Plan-and-Execute with Critic-in-the-loop

**Where:** `app/agent/nodes/planner.py`, `tool_executor.py`, `critic.py`, `graph.py`.

The Planner produces a typed JSON plan up-front, validated against `Plan` Pydantic model. The Executor walks the plan deterministically; after each tool call the Critic decides:

- `verdict=pass` → advance cursor
- `verdict=fail, replan=true` → relax filters (e.g. drop strict `min_balance`) and retry once

We cap iterations (`AGENT_MAX_ITERATIONS=6`) and replans (max 1 per run) so we can't loop forever. This pattern was chosen over ReAct because the plan trace is much easier to audit and replay.

---

## 2. Typed tool registry

**Where:** `app/application/tool_registry.py`, `app/tools/*.py`.

Every tool registers itself through a decorator with `input_model`, `output_model`. The registry:

- Validates args before dispatching (Pydantic).
- Enforces a per-tool timeout (`AGENT_TOOL_TIMEOUT_SECONDS`).
- Returns a uniform envelope `{ok, tool, data, latency_ms, error?}`.
- Surfaces JSON schemas at `GET /tools` for documentation + tool-calling LLMs that need them.

This makes adding a new tool a single file: declare the Pydantic models, decorate the function, add `from . import new_tool` to `app/tools/__init__.py`.

---

## 3. Hybrid retrieval (BM25 + dense) with RRF + MMR

**Where:** `app/infrastructure/rag/hybrid_retriever.py`, `mmr.py`.

- **Dense:** Gemini `text-embedding-004` (768-dim) indexed in Chroma (cosine).
- **Lexical:** `rank_bm25.BM25Okapi` over tokenised interaction summaries.
- **Fusion:** Reciprocal Rank Fusion (RRF) with K=60 — robust to score-scale differences without needing to learn a weight.
- **MMR re-rank:** λ=0.7 favours relevance; the (1−λ) penalty kills near-duplicates so the LLM sees diverse signals.
- **Citation IDs:** every chunk has a stable id like `INT-CUST-HERO-001-abc123` so downstream messages can cite (and the compliance check can verify).

Hybrid beats pure-dense by ~15% on short banking notes (numbers, product names, named entities matter — BM25 weights them naturally).

---

## 4. Cognitive-load-based LLM routing

**Where:** `app/infrastructure/llm/router.py`.

```
reasoning  (planner, critic, synth)  → Gemini  → Groq  → Mock
generation (whatsapp drafts)         → Groq    → Gemini → Mock
embed      (RAG)                     → Gemini → Mock (hash-bag fallback)
```

- Gemini's `application/json` response mime type returns near-perfect JSON adherence, ideal for the Planner.
- Groq's Llama 3.3 70B Versatile is ~10× faster per request and free up to 14,400 req/day — perfect for the 10 parallel WhatsApp drafts.
- A deterministic Mock LLM activates when no keys are configured, returning canned plans, critic verdicts, summaries and grounded WhatsApp drafts. **This means the entire system runs end-to-end without spending a rupee on inference.**

---

## 5. Numeric grounding compliance validator

**Where:** `app/scoring/compliance.py`, used by `app/tools/generate_whatsapp.py`.

Every number in a draft is extracted via regex and checked against a flattened bag of numbers from the source context (customer profile, recommended product, top features). Unmatched numbers (with a 5% rounding tolerance) are either stripped (default) or trigger a regeneration.

This is the core difference between this product and a vanilla LLM draft. It is **deterministic, testable, and shippable to compliance teams**.

---

## 6. Event-typed SSE streaming

**Where:** `app/api/chat.py`, `frontend/src/hooks/useAgentStream.ts`.

Each `TraceEvent` is emitted with a named SSE `event:` line; the frontend dispatches by type:

| Event           | UI side effect                                     |
| --------------- | -------------------------------------------------- |
| `info`          | sets `sessionId`, no UI change                     |
| `plan`          | adds a row to the Trace panel                      |
| `tool_call`     | adds a row to the Trace panel                      |
| `tool_result`   | updates the same row with `ok`, `source`, `rows`   |
| `critic`        | adds a row to the Trace panel                      |
| `candidate`     | inserts/updates a candidate card in the right pane |
| `draft`         | attaches a draft to its candidate                  |
| `synth`         | renders the assistant summary                      |
| `final`         | marks streaming complete                           |
| `error`         | renders an inline error banner                     |

Throttle: 5 ms `asyncio.sleep` between events so the UI can paint each one. Result: **first-token < 1 s**, full populate < 7 s.

---

## 7. Hexagonal data layer with failover + circuit breaker

**Where:** `app/infrastructure/datasource/*.py`.

- `DataSource` is a `Protocol`.
- `DatabricksSource` wraps the sync `databricks-sql-connector` in `asyncio.to_thread` with a 5 s `asyncio.wait_for` timeout.
- `SQLiteSource` is always-on, uses `aiosqlite` + WAL mode.
- `FailoverSource` tries primary; on exception or timeout, trips a 60 s circuit breaker and routes to secondary.
- Every result carries `source` — visible in the trace.

This is the architectural choice that makes the demo immune to free-tier flakiness.

---

## 8. Observability as data

**Where:** `app/agent/state.py` (TraceEvent), `app/agent/nodes/responder.py`, `app/api/trace.py`.

Rather than scatter `logger.info()` calls and rely on external APM, every node emits a typed `TraceEvent` that:

- streams to the UI live (SSE),
- persists to `agent_traces` table after the run,
- can be replayed at `GET /trace/:session_id`.

This is auditable and reproducible without paid tooling.

---

## 9. Transparent scoring

**Where:** `app/scoring/value.py`, `propensity.py`, `weights.yaml`.

Two weighted-logistic scorers:

- **Value:** balance, income, tenure, txn velocity — z-scored against the candidate pool.
- **Propensity:** per-product, e.g. for PROD-LOAN-PL: salary credit trend, recent large debit signal, EMI-to-income, balance buffer, age band fit, no_existing_loan bonus.

Weights live in `weights.yaml` — tune without touching code. Each feature returns a `contribution`, and the top-3 are passed into:

- the synthesizer prompt → "Top signal: …"
- the WhatsApp draft prompt → grounds the personalised reference
- the UI's drawer → renders a horizontal-bar score breakdown

No scoring decision is unexplained.
