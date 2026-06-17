# RM Copilot — Demo Video Script (~7 minutes)

Structured for a problem → solution → impact narrative, with explicit on-screen cues
(**what to show where**) and spoken narration for each segment.

---

## Pre-recording checklist

- [ ] Warm the backend: open `https://banking-crm-agent.onrender.com/healthz` once (free-tier cold start is ~50s).
- [ ] Confirm LLM quota is fresh — avoid running many test queries immediately before recording.
- [ ] For the WhatsApp segment: run locally with `frontend/.env.local` set, and stay logged into WhatsApp Web in the same browser (or set `VITE_DEMO_PHONES` in Vercel and redeploy).
- [ ] Browser at 100% zoom, notifications off, record at 1080p, start in dark theme.
- [ ] Have a mobile view ready (DevTools device toolbar) for the responsive segment.

---

## Segment 1 — Problem statement (0:00–0:50)

**Show:** Title slide, then the login screen.

**Say:**
> "Every retail bank runs on its Relationship Managers. Each RM owns 200 to 500 customers, and every morning they face the same two questions: *who should I call today, and what should I say?*
>
> Today they answer this manually — exporting CRM lists, eyeballing spreadsheets, guessing at propensity, and writing outreach by hand. It's slow, inconsistent, and in banking it carries compliance risk, because a single wrong number in a customer message is a regulatory problem.
>
> RM Copilot turns that entire workflow into one conversation."

---

## Segment 2 — Solution overview (0:50–1:30)

**Show:** Sign in with `shared`; the three-pane dashboard loads. Briefly toggle the theme; point across the panes.

**Say:**
> "RM Copilot is an agentic AI assistant. The RM asks in plain language, and the system decomposes the request, pulls live customer and transaction data, scores each customer transparently, recommends a product, and drafts a compliance-checked WhatsApp message — all streamed live so the reasoning is visible, not a black box.
>
> It's a full-stack build: React and Vite on the front end, FastAPI and an agent orchestrator on the back end, real LLMs with retrieval-augmented generation, deployed entirely on free tiers."

---

## Segment 3 — How we solved it, live (1:30–5:30)

### 3a. The canonical query (1:30–3:10)

**Show:** Type the exact assignment query and submit; let the live pipeline animate:
> `Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.`

**Say:**
> "Here's the assignment's own use case. Watch the pipeline below — this is the agent's real execution flow: Intent, Plan, Retrieve, Critic, Synthesize, Draft."

**Show:** Expand the "Agent reasoning" trace. Point to the planner, the five tool calls, the `source` and latency tags, and the hybrid RAG step.

**Say:**
> "The planner decomposed the request into five typed tool calls — query customers, score value, predict propensity, recommend product, and retrieve interaction notes. Each result is tagged with its data source and latency for auditability, and retrieval is hybrid: dense embeddings combined with keyword search."

### 3b. Identify high-value customers + conversion likelihood (3:10–3:50)

**Show:** Candidates populate on the right with composite-score rings. Click the top candidate to open Customer 360; point to the score-breakdown chart.

**Say:**
> "Candidates rank in real time. The composite score combines customer value and conversion propensity — and critically, it's transparent. This breakdown shows exactly which features drove the score. Nothing is hardcoded; these surface through real scoring of the underlying data."

### 3c. Recommend product + personalized, compliant outreach (3:50–4:40)

**Show:** In the drawer, point to the recommended product, then the WhatsApp draft and the "Compliance OK" badge. Click "Send on WhatsApp" — WhatsApp Web opens with the message pre-filled.

**Say:**
> "For each customer the agent recommends a suitable product and drafts a personalized WhatsApp message grounded in that customer's real signals. A compliance validator checks every number in the draft against the source data and strips anything ungrounded — directly addressing the regulatory risk I mentioned. The RM clicks send on WhatsApp, reviews, and sends: human in the loop."

### 3d. Stateful refinement — use case 2 (4:40–5:05)

**Show:** Same session, type:
> `Now narrow it to Bangalore customers and make the messages warmer.`

**Say:**
> "The system holds context. I don't repeat myself — I just refine. It re-plans with a city filter and a warmer tone, and the candidate list and drafts update accordingly."

### 3e. Reasoning, not hardcoding — use case 3 (5:05–5:30)

**Show:** New query:
> `Show me customers with a salary-credit slowdown — what should we offer them?`

**Say:**
> "And to prove it reasons: a salary slowdown is a retention signal, so the agent chooses an overdraft instead of a loan, and surfaces at-risk customers flagged for churn. Different intent, different product, different segment — driven by the data."

---

## Segment 4 — Breadth & robustness (5:30–6:30)

**Show:** (a) An out-of-scope query — `Write a poem about Mumbai rain` — politely declined. (b) A capability question — `What products can you recommend?` — grounded answer. (c) Open the Guide panel. (d) Switch to mobile view and use the bottom navigation.

**Say:**
> "Guardrails keep it on-task: anything outside banking is declined, and capability questions are answered from a grounded knowledge base. There's a Guide panel exposing every capability and a live system status. And the whole interface is responsive and theme-aware — usable by an RM in the field."

---

## Segment 5 — Architecture trade-offs & impact (6:30–7:30)

**Show:** The architecture diagram from the README.

**Say (architecture & trade-offs):**
> "Architecturally, it's hexagonal: ports and adapters let us fail over from Databricks to SQLite, and route across Gemini, Groq, and an offline mock, with no change to the agent. The trade-offs are deliberate — transparent heuristic scoring over a black-box model for auditability and reproducibility; typed tools over free-form SQL for safety; and graceful degradation everywhere, so a free-tier outage never breaks the demo."

**Say (impact):**
> "The impact: what takes an RM roughly ninety minutes of manual research every morning becomes a five-minute conversation — with a fully auditable trail that satisfies banking compliance. Scaled across thousands of RMs, that's a direct lift in outreach volume, conversion, and consistency. Thank you — the repository and live link are in the description."

---

## Exact queries (copy-paste)

1. `Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.`
2. `Now narrow it to Bangalore customers and make the messages warmer.` *(same session)*
3. `Show me customers with a salary-credit slowdown — what should we offer them?`
4. `Write a poem about Mumbai rain.` *(guardrail)*
5. `What products can you recommend?` *(FAQ)*

## Contingencies

- **Drafts show "mock":** LLM quota exhausted — pause, wait a few minutes, confirm a single call to `/tools/generate_whatsapp_message` returns `llm_route=groq`, then resume.
- **First query slow:** backend was cold — run one throwaway query to warm it.
- **WhatsApp "not on WhatsApp":** the customer is not mapped in `VITE_DEMO_PHONES`; use a mapped customer (Priya, Aarav, Ananya, Vikram, or Neha).

## Delivery tips

- Speak slightly slowly; pause 1–2 seconds after each segment to ease editing.
- Point with the cursor when saying "source", "Compliance OK", and "composite score".
- Target total length: 6–8 minutes (the assignment allows 5–10).
