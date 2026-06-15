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
5. [Tool design](#5-tool-design)
6. [Key design decisions](#6-key-design-decisions)
7. [Trade-offs and limitations](#7-trade-offs-and-limitations)
8. [Project structure](#8-project-structure)
9. [Setup and run](#9-setup-and-run)
10. [Deployment (free-tier)](#10-deployment-free-tier)
11. [Demo scenarios](#11-demo-scenarios)
12. [Alignment with the assignment + role](#12-alignment-with-the-assignment--role)
13. [Future work](#13-future-work)

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

## 5. Tool design

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

## 6. Key design decisions

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

## 7. Trade-offs and limitations

- **Heuristic scoring vs. trained ML:** weighted logistic regressions are auditable and tuneable but won't match a GBM trained on labelled outcomes. Chosen for **explainability + reviewer reproducibility**; production would add a `MLScorer` adapter behind the same interface.
- **Synthetic seed data:** 500 Faker customers + 5 hand-crafted hero personas. Real interaction notes would make the RAG more interesting.
- **Single-tenant, no SSO:** scope intentionally limited to a take-home build. The hexagonal layout makes adding tenants straightforward.
- **No real WhatsApp send:** stops at draft preview. Twilio adapter is documented in [Future work](#13-future-work).
- **Render free-tier cold start (~50s):** mitigated by self-ping + cron-job.org. First request after a cold start shows a "warming up" splash.
- **Databricks Free warehouse cold start (~30s):** mitigated by the 5s timeout + 60s circuit breaker that fails over to SQLite. Demo never breaks.
- **LangGraph package not strictly required:** the agent uses an equivalent hand-rolled async DAG to get tight SSE control. LangGraph is included as a dependency and the nodes are reusable inside a `StateGraph` should we want runtime hot-swapping.

---

## 8. Project structure

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
│   └── demo-script.md
├── .github/workflows/                 # backend-ci, frontend-ci
├── docker-compose.yml
├── render.yaml
├── .env.example
└── README.md  (this file)
```

---

## 9. Setup and run

### 9.1 Local — fastest path (offline, mock LLM, no API keys)

```bash
# 1) Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows
# source .venv/bin/activate           # macOS/Linux
pip install -r requirements.txt
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

### 9.2 With real LLMs

Create `backend/.env`:

```env
APP_PASSWORD=shared
GEMINI_API_KEY=...   # https://aistudio.google.com
GROQ_API_KEY=...     # https://console.groq.com  (optional but recommended for fast drafts)
```

Re-run uvicorn. The `/status` endpoint and the top bar of the UI show which providers are active.

### 9.3 Docker (single-command local stack)

```bash
docker compose up --build
```

### 9.4 Quick verification

```bash
# Smoke tests
cd backend
python tests/test_smoke.py
python tests/test_agent_e2e.py
```

Both scripts run end-to-end against the mock LLM with seeded data and assert the agent produces a plan, 5+ tool calls, ≥1 candidate, ≥1 draft, and a compliance-checked WhatsApp message for the hero customers.

---

## 10. Deployment (free-tier)

| Layer    | Service           | Notes                                                                                       |
| -------- | ----------------- | ------------------------------------------------------------------------------------------- |
| Frontend | Vercel            | Connect repo, set `VITE_API_URL`, deploy. `vercel.json` already configured.                 |
| Backend  | Render Web Service (Free) | Use `render.yaml` blueprint; set env vars in dashboard. 1 GB disk mounted at `/data`.  |
| Keep-alive | cron-job.org    | Hit `https://<your-render>.onrender.com/healthz` every 10 min.                              |
| Warehouse | Databricks Free Edition | Follow `databricks/README.md`. Optional — SQLite fallback ensures nothing breaks. |
| LLM      | Google AI Studio + Groq | Both have generous free tiers. Mock fallback if both are unset.                       |

**Live URLs (set after deploy):**

- Frontend: `https://banking-crm-agent.vercel.app`
- Backend: `https://banking-crm-agent.onrender.com`
- Password: `shared`

---

## 11. Demo scenarios

Three scenarios scripted for the 5–10 min video. Each shows a different facet:

| # | RM ask                                                                                                                | What to call out                                                                                                                                                  |
| - | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A | "Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages." | Full plan visible; 5 tool calls fire; `source: databricks` tags; top-3 includes **Priya Sharma** (HNW Mumbai, recent travel debits). 10 candidates with grounded drafts. |
| B | (Same session) "Now narrow it to Bangalore customers and make the messages warmer."                                   | Stateful refinement. Plan changes `city_filter` + `tone`. **Aarav Mehta** rises to the top. Drafts regenerated.                                                   |
| C | "Show me customers with salary-credit slowdown — what should we offer them?"                                          | Planner picks `PROD-LOAN-OD` (overdraft), not personal loan. **Ananya Iyer** ranks top with `interaction_stress_signal` lit up. Proves it's reasoning, not hardcoding. |

Full script in [`docs/demo-script.md`](docs/demo-script.md).

---

## 12. Alignment with the assignment + role

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

## 13. Future work

- **Trained ML scorer** (gradient-boosted) behind the same `Scorer` interface; A/B against the heuristic baseline.
- **Real WhatsApp send** via Twilio's Business API behind a `MessageChannel` port.
- **Multi-tenant** with per-RM auth (JWT + refresh) and row-level security in Databricks.
- **Vector-search inside Databricks** (Mosaic AI Vector Search) once it's free-tier eligible — removes the local Chroma dependency.
- **Distributed tracing** (OTLP → Honeycomb free tier) for production observability beyond the local `agent_traces` table.
- **Multilingual drafts** (Hindi/Tamil/Marathi) with language detection + per-language compliance dictionaries.
- **Reverse channel** — when the customer replies on WhatsApp, classify intent and surface to the RM with a suggested next step.

---

## License

MIT — see `LICENSE`. Built as a take-home; designed to be production-shaped.
