# Demo script (5–10 min)

Recording target: 7 minutes, Windows Game Bar → YouTube unlisted.

## Setup before recording

1. Run `python tests/test_agent_e2e.py` once to warm SQLite + Chroma indexes.
2. Hit `https://banking-crm-agent.onrender.com/healthz` to wake the Render free dyno.
3. Open the Vercel URL, sign in with password `shared`.
4. Open dev tools → Network → keep open to show streaming traffic if needed.

## Beat sheet

### 0:00–0:45 — Problem framing

"Indian retail banks have 40,000 RMs each managing hundreds of customers. Today the RM opens a static Salesforce report, manually filters, copy-pastes data into a WhatsApp template, and hopes the rate they mention is current. There is no audit trail, no personalization, and ChatGPT can't help because it can't access bank data and will hallucinate numbers — a regulatory non-starter.

This is the problem RM Copilot solves."

(Show landing/login page.)

### 0:45–1:15 — Architecture in 30 seconds

Open the architecture diagram (left-hand monitor or paste from `docs/architecture.mermaid`).

"Three layers: a Vercel-hosted React UI, a FastAPI backend running a LangGraph-style agent on Render, and a hexagonal data + LLM layer that fails over between Databricks ↔ SQLite and Gemini ↔ Groq ↔ a deterministic mock. Every node emits typed trace events that stream over SSE."

### 1:15–3:30 — Scenario A: canonical ask

Sign in. In the composer, paste:

> Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.

Narrate as the trace populates:

- **Plan**: "Notice the planner emits a JSON plan with intent, target product = `PROD-LOAN-PL`, and 5 ordered steps. Strict JSON mode — that's why we route Gemini, not Groq, for this node."
- **Tool calls**: "Each tool result shows `source: databricks` — that's the live warehouse. Latency for the warehouse calls is ~200ms; for the parallel propensity scorer it's ~340ms across 50 candidates."
- **Critic**: "After each tool we have an explicit verdict — pass or replan. This is what makes the reasoning audit-able."
- **Synthesizer**: "The agent's prose summary names the top 3 customers and quotes one signal per customer — straight from the feature contributions, not invented."

Open Priya Sharma's drawer:

- "Look at the score breakdown — five features with their contributions. The biggest one for her is `recent_large_debit_signal` (₹1.85L Mumbai travel) — that's the cue that she might be financing something soon."
- "On the WhatsApp draft, see the green compliance badge — every number in this draft is present in the source data. The validator is deterministic."
- Click "Edit", show that the RM can edit before approving, then click "Approve & queue".

### 3:30–5:00 — Scenario B: conversational refinement

Same session, paste:

> Now narrow it to Bangalore customers and make the messages warmer.

- "Notice the plan changes — `city_filter: ['Bangalore']`, `tone: warm`. The Critic skips the steps whose inputs haven't materially changed; the messages regenerate."
- "Aarav Mehta is now top of the list — his salary credits grew 23% YoY, and his SIP velocity tells us he's investing-minded, so the unsecured personal loan is a natural fit. The draft uses 'great to see your growth this year' — that's the warmer tone in action."

### 5:00–6:30 — Scenario C: retention play

Paste:

> Show me customers with salary-credit slowdown — what should we offer them?

- "Notice the planner did NOT pick PROD-LOAN-PL — it picked PROD-LOAN-OD (overdraft). That's the agent reasoning about the ask, not hardcoding."
- "Top of the list is Ananya Iyer — `salary_credit_dropping` and `interaction_stress_signal` both light up because her past interaction note says 'EMI stress'. The RAG retrieved that note as a citation."
- "Open her drawer and you can read the actual note. The WhatsApp draft starts with a defensive line — overdraft / liquidity buffer — not a sales pitch."

### 6:30–7:00 — Trace deep-dive + trade-offs

Open `/trace/:session_id` in a new tab.

"Every event is persisted. We can re-render this exact session offline, hand it to a compliance officer, or replay it in a regression test. This is our answer to 'no APM on free tier'."

Mention 3 trade-offs:
1. Heuristic scoring (transparent), production would add a trained model.
2. Mock LLM keeps the demo runnable with zero spend.
3. Databricks live, with SQLite failover when the warehouse cold-starts — the trace tells you which one served the call.

### 7:00 — Close

"That's RM Copilot — agentic AI for banking CRM in 7 minutes. The repo, README, and runbooks are at the URL on screen. Thanks."
