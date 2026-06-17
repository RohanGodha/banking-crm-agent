# RM Copilot — Demo Video Script (full technical walkthrough, ~8–9 minutes)

This script narrates the system end-to-end: the problem, the architecture and the
reasoning behind each choice (RAG, the LLMs, the databases, caching, the request
lifecycle), and then a complete live demo. Each segment lists **what to show** and
**what to say**.

---

## Pre-recording checklist

- [ ] Warm the backend: open `https://banking-crm-agent.onrender.com/healthz` once (free-tier cold start ~50s).
- [ ] Confirm LLM quota is fresh (avoid many test queries right before recording).
- [ ] WhatsApp segment: run locally with `frontend/.env.local` set and WhatsApp Web logged in, OR set `VITE_DEMO_PHONES` in Vercel and redeploy. Map at least one customer to your own number so the chat definitely opens (see the WhatsApp note at the end).
- [ ] Browser at 100% zoom, notifications off, 1080p, dark theme to start.
- [ ] Open the README architecture diagram in a second tab; have a mobile view ready (DevTools device toolbar).

---

## Part 1 — Problem statement (0:00–0:45)

**Show:** Title slide, then the login screen.

**Say:**
> "Every retail bank runs on its Relationship Managers. Each RM owns 200 to 500 customers, and every morning they ask the same two questions: who should I call today, and what should I say? Today that's manual — exporting CRM lists, guessing at propensity, and writing outreach by hand. It's slow, inconsistent, and in banking a single wrong number in a message is a compliance problem. RM Copilot turns that entire workflow into one conversation."

---

## Part 2 — Architecture and design rationale (0:45–2:45)

**Show:** The architecture diagram from the README.

### 2a. What we built and the high-level shape

**Say:**
> "The system has three layers. A React front end on Vercel; a FastAPI back end on Render that runs the agent; and a data and AI layer underneath. We used a hexagonal architecture — ports and adapters — so the agent never talks to a vendor directly. It talks to interfaces, and we can swap the database or the LLM behind them without touching the core."

### 2b. Why an agent, and why RAG + LLMs

**Say:**
> "Why an agent and not a single LLM call? Because the task is multi-step: retrieve data, score it, recommend a product, draft a message. So a planner decomposes the request into typed tool calls, an executor runs them, and a critic checks each result. The LLM does the reasoning and the language; the tools do the deterministic work against real data. RAG — retrieval-augmented generation — grounds the drafts: we retrieve each customer's real interaction notes so the message references actual behaviour, not a hallucination."

### 2c. Which LLMs, by provider — main and fallback

**Say:**
> "We use two LLM providers, by cognitive load. Google's Gemini 2.0 Flash handles reasoning — planning, criticism, synthesis — because it's reliable at structured JSON output, and Google's text-embedding-004 powers retrieval. Groq's Llama 3.3 70B handles generation — the WhatsApp drafts — because it's extremely fast and we fan out many drafts in parallel. Behind both sits a deterministic mock, so the whole pipeline runs offline with no API keys. The router tries the primary, then the secondary, then the mock, with per-provider rate limiting and one retry, so a free-tier limit degrades gracefully instead of breaking."

### 2d. Databases — what's stored where, and why

**Say:**
> "On data: the live store is SQLite in WAL mode — zero-cost, reliable, and the schema reseeds deterministically on every boot, which keeps the demo reproducible. For enterprise scale we have a Databricks Delta adapter behind the same interface, with automatic failover back to SQLite on a timeout. And for retrieval we use Chroma as a dense vector store combined with BM25 keyword search — hybrid retrieval, fused and re-ranked — over the interaction notes."

### 2e. Caching

**Say:**
> "For performance on a constrained tier, the settings, the LLM router, the data source, and the retrieval index are all cached singletons — built once and reused. The RAG corpus is embedded once at startup and held in memory, and prompts are cached too. SQLite's WAL mode keeps concurrent reads fast."

---

## Part 3 — Request lifecycle and analytics (2:45–3:30)

**Show:** The reasoning trace / live pipeline area (you can reference it now and again during the demo).

**Say:**
> "Here's the full lifecycle of one request. The query hits the FastAPI endpoint through an auth middleware — a shared-token gate. It enters the agent: first an intent router decides whether it's a task, a follow-up, an FAQ, or out of scope. For a task, the planner emits a typed plan; the executor runs each tool — querying customers, scoring value and propensity, recommending a product, and retrieving notes via RAG; the critic validates each step; the synthesizer ranks the candidates and writes the summary; and the message generator drafts the outreach. Every node emits a typed event that's streamed live to the UI over server-sent events — that's the analytics you'll see: the pipeline animation, the per-tool source and latency tags, and the transparent score breakdowns. The same events are persisted to a trace table for audit."

---

## Part 4 — Live demo (3:30–7:30)

### 4a. Login and interface (3:30–4:00)

**Show:** Sign in with `shared`. The three-pane dashboard loads. Toggle the theme once. Point across the panes.

**Say:**
> "Let's see it. I sign in — this is a single-tenant demo gate. Three panes: conversations on the left, the copilot in the center, candidates on the right. Full light and dark theming, and as we'll see, fully responsive."

### 4b. The canonical query — the full flow (4:00–5:40)

**Show:** Type the exact assignment query and submit; let the pipeline animate, then expand the reasoning trace.
> `Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.`

**Say:**
> "This is the assignment's own use case. Watch the pipeline: Intent, Plan, Retrieve, Critic, Synthesize, Draft. The planner broke this into five typed tool calls. Each tool result is tagged with its data source and latency. Retrieval is the hybrid RAG step."

**Show:** Candidates appear on the right. Click the top candidate → Customer 360 drawer. Point to the score breakdown, the recommended product, then the WhatsApp draft and the "Compliance OK" badge.

**Say:**
> "Candidates rank in real time by a composite of value and propensity — and it's transparent: this breakdown shows the exact features behind the score, nothing hardcoded. For each customer the agent recommends a product and drafts a personalized message grounded in that customer's real signals. The compliance validator checks every number against the source data and strips anything ungrounded — that's the regulatory safeguard."

### 4c. Send on WhatsApp (5:40–6:00)

**Show:** Click "Send on WhatsApp" → WhatsApp Web opens with the message pre-filled.

**Say:**
> "The RM clicks Send on WhatsApp — it opens WhatsApp Web with the message pre-filled. The RM reviews and sends: human in the loop, by design."

### 4d. Stateful refinement — use case 2 (6:00–6:25)

**Show:** Same session:
> `Now narrow it to Bangalore customers and make the messages warmer.`

**Say:**
> "The system holds context. I just refine — only Bangalore, warmer tone — and it re-plans; the candidates and drafts update."

### 4e. Reasoning, not hardcoding — use case 3 (6:25–6:50)

**Show:** New query:
> `Show me customers with a salary-credit slowdown — what should we offer them?`

**Say:**
> "And to prove it reasons: a salary slowdown is a retention signal, so the agent picks an overdraft instead of a loan and surfaces at-risk customers flagged for churn. Different intent, different product — driven by the data."

### 4f. Guardrails, FAQ, Guide (6:50–7:10)

**Show:** `Write a poem about Mumbai rain` (declined); `What products can you recommend?` (grounded answer); open the Guide panel.

**Say:**
> "Guardrails keep it on task — out-of-scope requests are declined, and capability questions are answered from a grounded knowledge base. The Guide panel exposes every capability and the live system status."

### 4g. Responsive / mobile (7:10–7:30)

**Show:** Enable the DevTools device toolbar → mobile view. Use the bottom navigation to switch panes; toggle the theme.

**Say:**
> "And it's fully responsive — bottom navigation on mobile, full theme support — so an RM can use it in the field."

---

## Part 5 — Trade-offs and impact (7:30–8:30)

**Show:** Architecture diagram again, or a closing slide.

**Say (trade-offs):**
> "The trade-offs were deliberate: transparent heuristic scoring over a black-box model, for auditability; typed tools over free-form SQL, for safety; and graceful degradation everywhere, so a free-tier outage never breaks the product."

**Say (impact):**
> "The impact: roughly ninety minutes of manual research each morning becomes a five-minute conversation, with a fully auditable trail that satisfies banking compliance. Scaled across thousands of RMs, that's a direct lift in outreach volume, conversion, and consistency. Thank you — the repository and live link are in the description."

---

## Exact queries (copy-paste)

1. `Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.`
2. `Now narrow it to Bangalore customers and make the messages warmer.` *(same session)*
3. `Show me customers with a salary-credit slowdown — what should we offer them?`
4. `Write a poem about Mumbai rain.` *(guardrail)*
5. `What products can you recommend?` *(FAQ)*

## Quick reference — the stack to name on camera

- **Front end:** React + Vite + TypeScript + Tailwind, Zustand state, SSE streaming, D3 visuals — on Vercel.
- **Back end:** FastAPI + Uvicorn (async), hexagonal agent orchestrator — on Render.
- **Middleware:** shared-token auth gate; server-sent events for streaming.
- **LLMs:** Google Gemini 2.0 Flash (reasoning) + text-embedding-004 (embeddings); Groq Llama 3.3 70B (drafts); deterministic mock fallback.
- **Databases:** SQLite (WAL) live store; Databricks Delta optional warehouse with failover; Chroma + BM25 for hybrid RAG.
- **Caching:** cached singletons for settings, router, data source, and the in-memory RAG index; cached prompts.

## Contingencies

- **Drafts show "mock":** quota exhausted — pause, wait, confirm `/tools/generate_whatsapp_message` returns `llm_route=groq`, resume.
- **First query slow:** backend was cold — run one throwaway query first.
- **WhatsApp "not on WhatsApp":** the customer isn't mapped, or the number isn't a registered WhatsApp account — see the WhatsApp note below; map a customer to your own number to guarantee the chat opens.
