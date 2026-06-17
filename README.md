# RM Copilot — Agentic AI for Banking CRM

> A conversational agent that helps a Relationship Manager (RM) identify high-value customers, score them transparently, and generate compliance-checked outreach — in one chat.

**The canonical demo:** RM Rohan types
> *"Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages."*
…and gets a ranked list of customers, each with an explainable score breakdown and a grounded WhatsApp draft, in under a few seconds.

---

## Table of contents

1. [The problem & why this product](#1-the-problem--why-this-product)
2. [Architecture diagram](#2-architecture-diagram)
3. [Execution flow](#3-execution-flow)
4. [AI patterns used](#4-ai-patterns-used)
5. [Prompt engineering](#5-prompt-engineering)
6. [Frontend & UX](#6-frontend--ux)
7. [Tool design](#7-tool-design)
8. [Key design decisions](#8-key-design-decisions)
9. [Trade-offs and limitations](#9-trade-offs-and-limitations)
10. [Project structure](#10-project-structure)
11. [Setup and run](#11-setup-and-run)
12. [Deployment (free-tier)](#12-deployment-free-tier)
13. [Demo scenarios](#13-demo-scenarios)
14. [Alignment with the assignment + role](#14-alignment-with-the-assignment--role)
15. [Future work](#15-future-work)

> **Live demo** · Frontend: <https://banking-crm-agent.vercel.app> · Backend: <https://banking-crm-agent.onrender.com> · Password: `shared`

---

## What's new (latest)

Most recent iteration focused on production polish, prompt robustness, and a real outreach path:

- **Light / dark theme switch** — CSS-variable token system, header + login toggle, persists to `localStorage`, follows OS preference, no flash on load. D3 visuals are theme-aware.
- **100% responsive UI (25+ improvements)** — mobile-first layout with a bottom tab bar (Chats / Copilot / Candidates), full 3-column workspace at `lg+`, fluid typography, safe-area insets for notched phones, accessible focus rings, `prefers-reduced-motion` support, and consistent Title-Case copy.
- **"Send on WhatsApp"** — the draft preview now opens **WhatsApp Web** with the message pre-filled (`web.whatsapp.com/send`); the RM reviews and presses send (human-in-the-loop). Demo numbers are mapped per customer via the `VITE_DEMO_PHONES` env var (kept out of the repo).
- **Few-shot Planner prompt** — two complete worked example plans (acquisition + retention) plus an explicit *“never emit `0` for unused numeric filters”* rule. Closes the last zero-shot gap and hardens plan generation.
- **Free-tier resilience** — token-bucket rate limiters on Groq (24 RPM) and Gemini (36 RPM) + one retry per provider before falling back, so parallel draft generation doesn't silently degrade to the mock under burst load. The `fallback_reason` is now surfaced in the API/trace when degradation happens.
- **Bug fixes** — `max_age=0` (and similar) no longer wipe out query results (sanitised in `query_customers` *and* discouraged in the prompt); plan-level `city_filter` is reliably injected into the query step so follow-ups like “now only Bangalore” actually filter.

---

## 1. The problem & why this product

Indian retail banks have ~40,000 Relationship Managers (RMs), each owning 200–500 customers. The RM's daily question is:

> "Who should I call today, and what should I say?"

Existing tools answer this badly:

| Existing tool                             | What it does                          | Why it fails the RM                                         |
| ----------------------------------------- | ------------------------------------- | ----------------------------------------------------------- |
| Salesforce / MS Dynamics CRM              | Static lead lists, manual filters     | No reasoning, no "why", no draft outreach                   |
| Banking BI dashboards (Tableau/Power BI)  | Pre-built reports                     | Backwards-looking; no per-customer action                   |
| Marketing automation (Braze, MoEngage)    | Mass-segment campaigns                | Generic copy, not RM-personal, no compliance grounding      |
| ChatGPT / Copilot Chat                    | General Q&A                           | No bank-data access, hallucinated numbers — regulatory non-starter |
| In-house ML lead scorers                  | Propensity scores                     | Black-box; no audit trail; RM doesn't trust the score       |

**RM Copilot** is the first tool that combines, in one chat surface:

1. **Live warehouse access** (Databricks Delta with SQLite failover)
2. **Transparent, explainable scoring** (top-3 feature contributions surfaced to RM and to the generated message)
3. **Compliance-validated message generation** (numeric grounding validator strips any number not present in source data)
4. **Stateful, conversational refinement** ("now narrow to Bangalore", "make the tone warmer")

**Measurable impact claim:** cuts the RM's daily "who to call" research from **~90 min to ~5 min**, with a fully audit-able trail that satisfies BFSI compliance.

---

## 2. Architecture diagram

```
                        ┌──────────────────────────────────────┐
                        │  Vercel  (React + Vite + shadcn UI)  │
                        │  /login (password gate)              │
                        │  /  → 3-pane dashboard               │
                        │  Streaming via fetch-event-source    │
                        └──────────────┬───────────────────────┘
                                       │  HTTPS, SSE, X-Access-Token
                        ┌──────────────▼───────────────────────┐
                        │  Render Web Service (FastAPI/Uvicorn)│
                        │  • Auth middleware (constant-time)   │
                        │  • Async everywhere                  │
                        │  • Agent orchestrator (LangGraph DAG)│
                        │  • Hexagonal ports + adapters        │
                        │  • Chroma (file, on mounted disk)    │
                        │  • SQLite WAL  (on mounted disk)     │
                        │  • Self-ping keep-alive              │
                        └──┬──────────┬──────────────┬─────────┘
                           │          │              │
              ┌────────────┘          │              └────────────┐
              ▼                       ▼                           ▼
   ┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │ LLM Router          │  │ DataSource Failover  │  │ Hybrid Retriever     │
   │ ─ Gemini 2.0 Flash  │  │ ─ Databricks SQL     │  │ ─ Chroma (dense)     │
   │   (Planner/Critic/  │  │   Connector (5s TO)  │  │ ─ BM25 (lexical)     │
   │    Synth, JSON mode)│  │ ─ SQLite WAL fallback│  │ ─ RRF + MMR re-rank  │
   │ ─ Groq Llama 3.3 70B│  │ ─ Source tag on every│  │ ─ Cited snippets     │
   │   (Messages, parallel│  │   tool result        │  │                      │
   │    fanout, <1s each)│  │ ─ 60s circuit breaker│  │                      │
   │ ─ Mock (offline)    │  │                      │  │                      │
   └─────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

A higher-resolution Mermaid version is in [`docs/architecture.mermaid`](docs/architecture.mermaid).

---

## 3. Execution flow

A single RM query exercises this sequence:

```
RM ──▶ POST /chat/stream { rm_query }
       │
       ▼
   ┌─────────────┐   produces  Plan{ intent, target_product, steps[1..5] }
   │  Planner    │ ─── LLM (Gemini, JSON mode) ────────────────────────┐
   └─────────────┘                                                     │
       │                                                               │
       ▼                                                               │
   ┌──────────────────────────────────────┐                            │
   │  Tool Executor  (loops over steps)   │                            │
   │  step 1  query_customers             │  source: databricks|sqlite │
   │  step 2  compute_customer_value      │  parallel asyncio.gather   │
   │  step 3  predict_loan_propensity     │  per candidate             │
   │  step 4  recommend_products          │  eligibility-checked       │
   │  step 5  search_interactions         │  hybrid RAG, MMR re-rank   │
   └─────────────┬────────────────────────┘                            │
                 │                                                     │
                 ▼                                                     │
   ┌─────────────┐  verdict pass | replan? Loop or proceed             │
   │  Critic     │ ── LLM (Gemini, JSON mode) ─────────────────────────┘
   └─────────────┘
                 │
                 ▼
   ┌─────────────────────────────┐  ranks candidates by composite (value+propensity),
   │  Synthesizer                │  attaches top-3 features + citations,
   │                             │  produces a ≤120-word RM summary.
   └─────────────┬───────────────┘  (LLM: Gemini)
                 │
                 ▼
   ┌─────────────────────────────┐  parallel fanout via asyncio.gather:
   │  Message Generator (×N)     │   one Groq call per candidate, then
   │                             │   the compliance validator strips any
   │                             │   number that isn't in the source context.
   └─────────────┬───────────────┘
                 │
                 ▼
   ┌─────────────────────────────┐  persists drafts + agent_traces; emits
   │  Responder                  │  the final SSE envelope to the UI.
   └─────────────────────────────┘
```

Every node emits a typed `TraceEvent` that is streamed live over SSE. The frontend's right pane fills in progressively — candidates appear as soon as the synthesizer ranks them.

---

## 4. AI patterns used

The system deliberately combines well-known patterns rather than inventing new ones — each one earns its place in the rubric.

### 4.0 Intent-routed multi-prompt architecture

Every message first hits an **intent gate** (heuristic + LLM `INTENT_PROMPT`) that routes to one of five paths — so a greeting never triggers a customer hunt:

| Intent | Handler | Prompt |
|---|---|---|
| `task` | full agent pipeline | `PLANNER_PROMPT` (MASTER_AGENT) |
| `follow_up` | rewrite-with-history → pipeline | `FOLLOW_UP_PROMPT` |
| `faq` | grounded answer from KB | `FAQ_PROMPT` + `faq_kb.py` |
| `chitchat` | conversational reply | (templated) |
| `out_of_scope` | safe decline | `GUARDRAIL_PROMPT` |

All prompts live in a single versioned registry: `app/agent/prompts.py` (`SYSTEM_PROMPT`, `INTENT_PROMPT`, `PLANNER_PROMPT`/`MASTER_AGENT_PROMPT`, `FOLLOW_UP_PROMPT`, `CRITIC_PROMPT`, `SYNTHESIZER_PROMPT`, `WHATSAPP_PROMPT`, `FAQ_PROMPT`, `GUARDRAIL_PROMPT`). Conversation history is loaded per session so `follow_up` refinements ("now only Bangalore, warmer tone") are rewritten into standalone tasks. Pattern adapted from a production VFS RAG bot (query-rewriting + intent routing + grounded FAQ) and an insurance multi-agent classifier.

### 4.0b Sentiment / churn-risk escalation + multilingual outreach

- **Sentiment & churn-risk**: each candidate's interaction notes are analysed (rule-based, offline-safe) and tagged `positive | neutral | negative` with an `escalate` flag for churn-risk customers — surfaced as a badge so the RM prioritises retention calls. (Pattern adapted from the VFS bot's sentiment/live-agent routing.)
- **Multilingual drafts**: the planner detects a requested language ("…in Hindi") and the WhatsApp generator writes the entire message in that language (English default). Fits Indian multi-lingual outreach.

### 4.1 Plan-and-Execute with Critic-in-the-loop

- **Pattern:** *Planner emits a typed JSON plan → Executor runs each step → Critic decides pass/replan.*
- **Why:** ReAct loops are hard to audit; plain function-calling has no reasoning trace; LangGraph-style stateful DAG gives explicit nodes that can be replayed via `/trace/:session`.
- **Implementation:** `app/agent/nodes/planner.py`, `critic.py`, `tool_executor.py`.

### 4.2 Typed tools + parallel dispatch

- Every tool exposes Pydantic IO models; their JSON schemas are auto-exported at `GET /tools`.
- Independent calls fanned out via `asyncio.gather` (e.g. scoring N candidates).
- Every tool result tagged with `{source, latency_ms, rows}` so the trace surfaces provenance.

### 4.3 Hybrid retrieval (BM25 + dense) with RRF + MMR

- **Why hybrid:** dense alone misses keyword cues; lexical alone misses semantic paraphrases. Reciprocal Rank Fusion (RRF) is robust to score-scale differences.
- **Why MMR (λ=0.7):** removes near-duplicates and surfaces diverse signal across interaction notes.
- **Implementation:** `app/infrastructure/rag/hybrid_retriever.py`.

### 4.4 Cognitive-load-based LLM routing

- **Reasoning** nodes → Gemini 2.0 Flash (best structured-output adherence among free tiers).
- **Generation** nodes → Groq Llama 3.3 70B (sub-second per draft, parallelisable, 14,400 req/day free).
- **Embeddings** → Gemini `text-embedding-004`.
- **Offline mock** → deterministic fallback so the whole pipeline runs without keys.
- **Auto-failover** between providers; the active route is surfaced on every event.

### 4.5 Grounded generation + numeric compliance validator

- WhatsApp prompt forbids inventing numbers.
- After generation, every number in the draft is checked against a flattened bag of numbers in the source context (customer + product + feature values).
- Ungrounded numbers are stripped; the trace marks the draft as `compliance.ok=false`. **This is the #1 BFSI compliance failure of generic LLM drafts.**

### 4.6 Event-typed SSE streaming

- Single channel multiplexes `plan`, `tool_call`, `tool_result`, `critic`, `synth`, `candidate`, `draft`, `final`, `error`.
- UI dispatches by event type → no full re-renders → first-token latency under 1 s.

### 4.7 Hexagonal data layer with failover + circuit breaker

- `DataSource` is a Pydantic Protocol. Adapters: `SQLiteSource`, `DatabricksSource`. Composite: `FailoverSource` with a 5 s primary timeout and 60 s breaker.
- The reviewer literally sees `source: databricks` flip to `source: sqlite(failover)` when the warehouse is cold. The product **never breaks**.

### 4.8 Custom observability — the trace is data

- Every node writes a `TraceEvent` to the `agent_traces` table.
- `/trace/:session_id` returns the full DAG execution as JSON — replay-friendly, audit-friendly. This is the answer to "no paid APM on the free tier".

### 4.9 Transparent scoring

- Two heuristic scorers, both weighted-logistic with weights in `app/scoring/weights.yaml`.
- Returns top contributing features per candidate; those features feed both the synthesizer's prose summary and the WhatsApp draft. **No black-box numbers reach the RM.**

---

## 5. Prompt engineering

All prompts live in one versioned registry — `app/agent/prompts.py` (plus the larger node prompts as Markdown in `app/agent/prompts/`). Each prompting technique is matched to the task that needs it:

| Technique | Where it's used | Why there |
|---|---|---|
| **System / persona prompt** | `SYSTEM_PROMPT` — shared base persona ("You are RM Copilot…") | Consistent voice + guardrails across every node |
| **Role prompting** | Per-node roles — "You are the **Planner**", "the **Critic**", WhatsApp "experienced Indian banking RM" | Focuses each LLM call on one job |
| **Few-shot** | `FOLLOW_UP_PROMPT` (2 examples), `INTENT_PROMPT` (per-class examples), **`PLANNER` (2 full worked plans)** | Rewriting, classification, and planning are far more reliable with exemplars |
| **Zero-shot** | `CRITIC`, `SYNTHESIZER`, `GUARDRAIL`, `FAQ` | Clear instructions + constraints are enough; examples would just add tokens |
| **Structured output (JSON-mode)** | `INTENT`, `PLANNER`, `CRITIC`, `FOLLOW_UP` | Output is consumed by deterministic code, so strict JSON schemas are enforced |
| **Task decomposition (plan-and-execute)** | `PLANNER` | Turns a natural-language ask into a typed multi-step tool plan |
| **RAG / grounding** | `FAQ_PROMPT` (KB injected), `WHATSAPP` (context-grounded), `SYNTHESIZER` (candidate list verbatim) | Stops hallucination; answers are tied to real data |
| **Reflection / self-critique** | `CRITIC_PROMPT` | Evaluates each tool result and decides pass / replan |
| **Router / classification** | `INTENT_PROMPT` | Routes every message into one of 5 paths before any work happens |
| **Guardrail / refusal** | `GUARDRAIL_PROMPT` + negative constraints ("Never invent numbers") everywhere | Safe out-of-scope declines; BFSI safety |
| **Output constraints** | Word limits (≤90/120/25), "no emojis", anti-placeholder rules | Predictable, clean, RM-ready output |

The Planner prompt carries an explicit hardening rule learned from a real bug: **never emit `0` for an unused numeric filter** (a `max_age: 0` once silently returned zero customers) — enforced both in the prompt and sanitised in the `query_customers` tool (defense-in-depth).

---

## 6. Frontend & UX

React + Vite + Tailwind, Zustand store, SSE streaming. Recent UX work:

- **Light / dark theme** — color tokens are CSS variables (`--c-*`) swapped per theme; a `ThemeToggle` in the header and login; persisted to `localStorage`; follows the OS preference until the user chooses; no flash on load (inline pre-paint script). D3 visuals read the active theme's colors.
- **100% responsive** — mobile-first single-pane layout with a **bottom tab bar** (Chats / Copilot / Candidates), expanding to the full 3-column workspace at `lg+`; fluid typography via `clamp()`; safe-area insets (`env(safe-area-inset-*)`) for notched phones; thinner scrollbars on touch; drawers go full-width on mobile.
- **Accessibility** — visible `:focus-visible` rings, `prefers-reduced-motion` support, ARIA labels on nav/toggle.
- **Live agent visuals** — a D3 pipeline (Intent→Plan→Retrieve→Critic→Synthesize→Draft) animates as events stream; a D3 "thinking" loader; a collapsible reasoning trace.
- **WhatsApp outreach** — draft preview with edit, copy, and **Send on WhatsApp** (opens WhatsApp Web pre-filled; RM presses send). Per-customer demo numbers come from `VITE_DEMO_PHONES` (never committed).
- **Consistent copy** — Title-Cased labels throughout; fixed page title and meta.

---

## 7. Tool design

| Tool                                | Purpose                                                      | Input fields                                                                                       |
| ----------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `query_customers`                   | Filtered shortlist from the warehouse                        | `cities`, `segments`, `min_income`, `min_balance`, `min_age`, `max_age`, `exclude_products`, `limit` |
| `get_transactions`                  | Recent transactions + per-category aggregates                | `customer_id`, `months`                                                                            |
| `compute_customer_value`            | Explainable value score per customer                         | `customer_ids`, `months`                                                                           |
| `predict_loan_propensity`           | Per-product propensity score + driving features              | `customer_ids`, `product_id`                                                                       |
| `recommend_products`                | Eligibility-checked best product per customer                | `customer_ids`, `candidate_product_ids?`, `top_k`                                                  |
| `search_interactions`               | Hybrid RAG over interaction notes (with citations)           | `query`, `k`, `customer_id?`                                                                       |
| `generate_whatsapp_message`         | Compliance-validated draft for one customer + product        | `customer_id`, `product_id`, `tone`, `top_features`, `rm_name`                                     |
| `create_outreach_batch`             | Persists drafts against a session                            | `session_id`, `channel`, `drafts[]`                                                                |

All schemas are introspectable at `GET /tools`. Every tool returns a `latency_ms` and `source` field that flows into the trace panel.

---

## 8. Key design decisions

| Decision                                                                                  | Why                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hexagonal architecture (`DataSource`, `LLMClient` ports + adapters)**                   | Lets us swap Databricks ↔ SQLite ↔ in-memory and Gemini ↔ Groq ↔ Mock without touching the agent or tools. Survives free-tier outages.                              |
| **Stateful DAG agent (Planner → loop(Executor → Critic) → Synth → MessageGen → Responder)** | Explicit nodes satisfy "structured reasoning flow"; replayable trace satisfies "state/context handling"; modularity satisfies "extensible design".                  |
| **Dual-LLM routing by cognitive load**                                                    | Best free-tier price/performance: Gemini's JSON-mode reliability for plans, Groq's latency for parallel drafts.                                                       |
| **Numeric grounding compliance validator**                                                | BFSI requires no fabricated rates. Catching this in code (not prompting) makes the guarantee verifiable and testable.                                                |
| **Transparent weighted scoring (YAML weights)**                                           | Tuneable without code changes; feature contributions feed the LLM summary and the WhatsApp draft; passes the "no hardcoded outputs without reasoning" disqualifier. |
| **Event-typed SSE**                                                                       | Lets the UI populate progressively, gives first-token <1 s perceived latency, makes the agent feel "live".                                                            |
| **Self-ping keep-alive + cron-job.org backup**                                            | Prevents Render free-tier sleep mid-demo. Cheap belt-and-braces.                                                                                                     |
| **Shared-password auth (`X-Access-Token`)**                                               | Adequate for a single-tenant demo; stops randoms burning your Gemini quota. Trivially upgradable to JWT later.                                                       |

---

## 9. Trade-offs and limitations

- **Heuristic scoring vs. trained ML:** weighted logistic regressions are auditable and tuneable but won't match a GBM trained on labelled outcomes. Chosen for **explainability + reviewer reproducibility**; production would add a `MLScorer` adapter behind the same interface.
- **Synthetic seed data:** 500 Faker customers + 5 hand-crafted hero personas. Real interaction notes would make the RAG more interesting.
- **Single-tenant, no SSO:** scope intentionally limited to a take-home build. The hexagonal layout makes adding tenants straightforward.
- **WhatsApp = click-to-send, not programmatic:** the "Send on WhatsApp" button opens WhatsApp Web with the message pre-filled (`web.whatsapp.com/send`) — the RM reviews and presses send (intentional human-in-the-loop). Fully automated sending via the Twilio / Meta Cloud API behind a `MessageChannel` port is documented in [Future work](#15-future-work). Demo numbers are mapped per customer via `VITE_DEMO_PHONES`; without it, hero customers use synthetic seed numbers (WhatsApp may show "not on WhatsApp").
- **Free-tier LLM rate limits:** under heavy back-to-back use, Groq/Gemini free quotas can throttle. Token-bucket limiters (Groq 24 RPM, Gemini 36 RPM) + one retry per provider smooth bursts, and the router degrades gracefully to the deterministic mock (never crashes). When that happens the `fallback_reason` is surfaced in the trace/API.
- **Render free-tier cold start (~50s):** mitigated by self-ping + cron-job.org. First request after a cold start shows a "warming up" splash.
- **Databricks Free warehouse cold start (~30s):** mitigated by the 5s timeout + 60s circuit breaker that fails over to SQLite. Demo never breaks.
- **LangGraph package not strictly required:** the agent uses an equivalent hand-rolled async DAG to get tight SSE control. LangGraph is included as a dependency and the nodes are reusable inside a `StateGraph` should we want runtime hot-swapping.

---

## 10. Project structure

```
banking-crm-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint
│   │   ├── settings.py                # pydantic-settings
│   │   ├── auth/                      # shared-password middleware
│   │   ├── api/                       # routers (chat, sessions, customers, trace, tools, outreach, health)
│   │   ├── domain/                    # Pydantic models
│   │   ├── application/tool_registry  # @tool decorator + invoke_tool()
│   │   ├── infrastructure/
│   │   │   ├── datasource/            # base, sqlite, databricks, failover, factory
│   │   │   ├── llm/                   # base, gemini, groq, mock, router
│   │   │   └── rag/                   # hybrid_retriever, mmr
│   │   ├── agent/
│   │   │   ├── graph.py               # async DAG
│   │   │   ├── state.py               # AgentState, TraceEvent
│   │   │   ├── nodes/                 # planner, tool_executor, critic, synthesizer, message_generator, responder
│   │   │   └── prompts/               # versioned .md prompts
│   │   ├── tools/                     # 8 typed tools
│   │   ├── scoring/                   # value, propensity, compliance, weights.yaml
│   │   ├── db/                        # schema.sql, seeders, sqlite_engine
│   │   └── observability/             # logger
│   ├── tests/
│   │   ├── test_smoke.py              # tool registry + scoring + WhatsApp gen
│   │   └── test_agent_e2e.py          # full LangGraph-style run with mock LLM
│   ├── scripts/export_sqlite_to_csv.py # for Databricks seeding
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/{Login,Dashboard}.tsx
│   │   ├── features/                  # chat, trace, candidates, drawer, sessions
│   │   ├── hooks/useAgentStream.ts    # SSE consumer
│   │   ├── lib/                       # api, format, types, cn
│   │   └── store/uiStore.ts           # Zustand
│   ├── package.json
│   └── vercel.json
├── databricks/
│   ├── notebooks/01_seed_delta.py
│   └── README.md
├── docs/
│   ├── architecture.mermaid
│   ├── execution-flow.md
│   ├── ai-patterns.md
│   ├── tradeoffs.md
│   ├── demo-script.md
│   └── video-script.md             # beat-by-beat recording script
├── .github/workflows/                 # backend-ci, frontend-ci
├── docker-compose.yml
├── render.yaml
├── .env.example
└── README.md  (this file)
```

---

## 11. Setup and run

### 11.1 Local — fastest path (offline, mock LLM, no API keys)

```bash
# 1) Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows
# source .venv/bin/activate           # macOS/Linux
pip install -r requirements.txt
# Optional — full dense+BM25 hybrid RAG (otherwise BM25-only fallback is used):
# pip install -r requirements-rag.txt
$env:PYTHONPATH = "."                  # Windows PS
# export PYTHONPATH=.                  # macOS/Linux
uvicorn app.main:app --reload --port 8000

# 2) Frontend (new shell)
cd frontend
npm install
$env:VITE_API_URL = "http://localhost:8000"
# export VITE_API_URL=http://localhost:8000
npm run dev
```

Open <http://localhost:5173>, sign in with password **`shared`**, and ask one of the three quick-prompts.

**Optional — make "Send on WhatsApp" open a real chat:** copy `frontend/.env.example` to `frontend/.env.local` and map demo customers (by first name) to real test numbers:

```env
# digits only, with country code, no "+"/spaces
VITE_DEMO_PHONES={"Priya":"919876543210","Ananya":"919812345678"}
```

`.env.local` is gitignored, so real numbers never reach the repo. Be logged into WhatsApp Web in the same browser. (Theme: the light/dark toggle is in the header and login — persists automatically.)

### 11.2 With real LLMs

Create `backend/.env`:

```env
APP_PASSWORD=shared
GEMINI_API_KEY=...   # https://aistudio.google.com
GROQ_API_KEY=...     # https://console.groq.com  (optional but recommended for fast drafts)
```

Re-run uvicorn. The `/status` endpoint and the top bar of the UI show which providers are active.

### 11.3 Docker (single-command local stack)

```bash
docker compose up --build
```

### 11.4 Quick verification

```bash
# Smoke tests
cd backend
python tests/test_smoke.py
python tests/test_agent_e2e.py
```

Both scripts run end-to-end against the mock LLM with seeded data and assert the agent produces a plan, 5+ tool calls, ≥1 candidate, ≥1 draft, and a compliance-checked WhatsApp message for the hero customers.

---

## 12. Deployment (free-tier)

| Layer    | Service           | Notes                                                                                       |
| -------- | ----------------- | ------------------------------------------------------------------------------------------- |
| Frontend | Vercel            | Connect repo, set `VITE_API_URL` (and optionally `VITE_DEMO_PHONES` for live WhatsApp send), deploy. `vercel.json` already configured. Env vars are build-time — redeploy after changing them. |
| Backend  | Render Web Service (Free) | Use `render.yaml` blueprint; set env vars in dashboard. Ephemeral FS — `bootstrap()` reseeds deterministically on each boot. |
| Keep-alive | cron-job.org    | Hit `https://<your-render>.onrender.com/healthz` every 10 min.                              |
| Warehouse | Databricks Free Edition | Follow `databricks/README.md`. Optional — SQLite fallback ensures nothing breaks. |
| LLM      | Google AI Studio + Groq | Both have generous free tiers. Mock fallback if both are unset.                       |

**Live URLs (set after deploy):**

- Frontend: `https://banking-crm-agent.vercel.app`
- Backend: `https://banking-crm-agent.onrender.com`
- Password: `shared`

---

## 13. Demo scenarios

Three scenarios scripted for the 5–10 min video. Each shows a different facet:

| # | RM ask                                                                                                                | What to call out                                                                                                                                                  |
| - | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A | "Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages." | Full plan visible; 5 tool calls fire; `source: databricks` tags; top-3 includes **Priya Sharma** (HNW Mumbai, recent travel debits). 10 candidates with grounded drafts. |
| B | (Same session) "Now narrow it to Bangalore customers and make the messages warmer."                                   | Stateful refinement. Plan changes `city_filter` + `tone`. **Aarav Mehta** rises to the top. Drafts regenerated.                                                   |
| C | "Show me customers with salary-credit slowdown — what should we offer them?"                                          | Planner picks `PROD-LOAN-OD` (overdraft), not personal loan. **Ananya Iyer** ranks top with `interaction_stress_signal` lit up. Proves it's reasoning, not hardcoding. |

Full script in [`docs/demo-script.md`](docs/demo-script.md).

---

## 14. Alignment with the assignment + role

### Assignment rubric (`Take-Home Assignment_ Agentic AI for Banking CRM-1.pdf`)

| Criterion              | Where it lives                                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Task decomposition     | LangGraph-style DAG with explicit Planner → Tools → Critic → Synth → MessageGen → Responder. JSON plan is replayable.                       |
| Effective tool/API use | 8 typed tools with Pydantic IO, registered through a decorator, introspectable at `/tools`, parallel-dispatched, source-tagged.             |
| Structured reasoning   | Every node emits a typed `TraceEvent`; the trace panel renders the live reasoning; full history saved to `agent_traces`.                    |
| State/context handling | `AgentState` is JSON-serialisable; persisted per session; `/trace/:id` replays it; refinement queries reuse the session.                   |
| Modular & extensible   | Hexagonal ports (`DataSource`, `LLMClient`), tool registry, YAML-tuned weights — add a provider/tool/feature without touching the core.    |
| Output quality         | Compliance validator enforces grounded numbers; feature contributions feed the prose summary AND the per-customer WhatsApp draft.           |
| Documentation          | This README + `docs/*.md` + Mermaid + demo script + CI proving the smoke + E2E tests pass.                                                  |
| **No hardcoded outputs** | Hero customers reach the top through **real scoring** of seeded signals. The seeder is reproducible (`Faker.seed(7)`).                    |

### Role expectations (`AI Fullstack builder Engineer.pdf`)

| Expectation                                              | How this repo demonstrates it                                                                                                                                                                            |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AI-native: LLMs, copilots, automation workflows          | The product *is* an LLM-powered copilot end-to-end.                                                                                                                                                       |
| End-to-end ownership (ideation → production rollout)     | This README, the plan history, the deploy blueprints (`render.yaml`, `vercel.json`), and the CI workflows all show a single builder driving 0→1.                                                          |
| Frontend + backend + APIs + data                         | React + Vite + Tailwind + shadcn-style UI · FastAPI + LangGraph-style agent · Pydantic-typed APIs · Databricks Delta + SQLite + Chroma data layer.                                                       |
| BFSI / CRM / SaaS impact                                 | Use case is a CRM-flavoured agent for Indian retail banking, with compliance-aware drafting and an explainable scoring story tuned for BFSI audit requirements.                                          |
| Rapid prototyping → product-market fit                   | Mock LLM lets reviewers exercise the full agent without API keys. The seeded hero customers + 3-scenario demo script ground the value prop in a concrete workflow.                                       |
| Real-world impact at scale                               | The architectural moves (parallel asyncio fanout, RRF+MMR hybrid RAG, circuit breaker, embedding cache, self-ping keep-alive) are exactly the scalability levers that a production rollout would use. |

---

## 15. Future work

- **Fully automated WhatsApp send** via Twilio / Meta Cloud API behind a `MessageChannel` port (today it's click-to-send via WhatsApp Web — human-in-the-loop).
- **Trained ML scorer** (gradient-boosted) behind the same `Scorer` interface; A/B against the heuristic baseline.
- **Multi-tenant** with per-RM auth (JWT + refresh) and row-level security in Databricks.
- **Vector-search inside Databricks** (Mosaic AI Vector Search) once it's free-tier eligible — removes the local Chroma dependency.
- **Distributed tracing** (OTLP → Honeycomb free tier) for production observability beyond the local `agent_traces` table.
- **Per-language compliance dictionaries** — multilingual drafts already ship (planner detects the language and the generator writes in it); next is language-specific number/term grounding.
- **Reverse channel** — when the customer replies on WhatsApp, classify intent and surface to the RM with a suggested next step.

> Already shipped this iteration: light/dark theme, 100% responsive UI, "Send on WhatsApp" (click-to-send), few-shot Planner, token-bucket rate limiting + graceful fallback, and the `max_age=0` / `city_filter` fixes — see [What's new](#whats-new-latest).

---

## License

MIT — see `LICENSE`. Built as a take-home; designed to be production-shaped.
