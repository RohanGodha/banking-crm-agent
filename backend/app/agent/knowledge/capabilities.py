"""Structured capabilities + 50 real FAQs.

Single source consumed by:
  - the FAQ node (grounding text),
  - the /meta/capabilities + /meta/faqs API,
  - the frontend "Guide" panel (what the agent does, products, examples, FAQs).
"""
from __future__ import annotations

CAPABILITIES: list[dict[str, str]] = [
    {"title": "Find customers", "desc": "Search the base by city, segment, income, balance, age, risk appetite, or product holdings."},
    {"title": "Score value", "desc": "Rank customers by an explainable value score (balance, income, tenure, transaction velocity)."},
    {"title": "Predict conversion", "desc": "Estimate per-product propensity to convert, with the top driving features shown."},
    {"title": "Recommend products", "desc": "Suggest the best-fit, eligibility-checked product for each customer."},
    {"title": "Draft outreach", "desc": "Generate a personalised, compliance-checked WhatsApp message per customer."},
    {"title": "Refine conversationally", "desc": "Follow-ups like 'now only Bangalore' or 'make it warmer' build on the previous result."},
    {"title": "Flag churn risk", "desc": "Detect negative sentiment / churn signals in interaction notes and flag for retention."},
    {"title": "Multilingual drafts", "desc": "Write outreach in Hindi, Marathi, Tamil and more — English by default."},
    {"title": "Explain every score", "desc": "Show the top contributing features so you understand the 'why' behind each ranking."},
    {"title": "Show its reasoning", "desc": "Stream the full plan -> tools -> critic -> synthesis trace, replayable per session."},
]

PRODUCTS: list[dict[str, str]] = [
    {"id": "PROD-LOAN-PL", "name": "Personal Loan", "category": "loan"},
    {"id": "PROD-LOAN-HL", "name": "Home Loan", "category": "loan"},
    {"id": "PROD-LOAN-OD", "name": "Personal Overdraft", "category": "overdraft"},
    {"id": "PROD-CARD-PREM", "name": "Privilege Credit Card", "category": "card"},
    {"id": "PROD-CARD-CB", "name": "Cashback Credit Card", "category": "card"},
    {"id": "PROD-INV-SIP", "name": "Equity SIP", "category": "investment"},
    {"id": "PROD-INV-FD", "name": "Fixed Deposit", "category": "investment"},
]

EXAMPLE_PROMPTS: list[str] = [
    "Find high-value customers likely to convert for a personal loan this month and draft WhatsApp messages.",
    "Show affluent customers in Bangalore for a premium credit card.",
    "Which customers show salary-credit slowdown — what should we offer them?",
    "Find HNW customers in Mumbai with idle surplus for an Equity SIP.",
    "Top 5 customers for a cashback credit card, draft messages in Hindi.",
    "Customers with no credit card and high UPI spends — recommend a card.",
]

DOMAIN = {
    "name": "Retail Banking — Relationship Manager CRM",
    "persona": "RM Copilot, assistant to RM Rohan at an Indian retail bank",
    "scope": "Customer targeting, conversion scoring, product recommendation, and outreach drafting.",
    "out_of_scope": "General knowledge, coding, other industries, legal/credit decisions, or actually sending messages.",
}

# --- 50 FAQs (grouped) ---
FAQS: list[dict[str, str]] = [
    # Capability
    {"q": "What can you do?", "a": "I find high-value customers, score their likelihood to convert, recommend products, and draft compliance-checked WhatsApp outreach — with full reasoning shown.", "category": "Capabilities"},
    {"q": "List the things you can help me with.", "a": "Find customers; score value; predict conversion propensity; recommend products; draft WhatsApp outreach; refine results conversationally; flag churn risk; write multilingual drafts; explain every score; and show my step-by-step reasoning.", "category": "Capabilities"},
    {"q": "How do I ask for customers?", "a": "Ask in plain language, e.g. 'Find affluent customers in Pune for a personal loan'. I infer the filters and the target product.", "category": "Capabilities"},
    {"q": "Can you refine a result?", "a": "Yes. After a search, say 'now only Mumbai', 'top 5 only', 'make it warmer', or 'exclude existing cardholders' and I'll rebuild on the previous result.", "category": "Capabilities"},
    {"q": "Can you draft the message for me?", "a": "Yes — every candidate gets a personalised WhatsApp draft grounded in their real signals, which you can edit and approve.", "category": "Capabilities"},
    {"q": "Do you send the WhatsApp messages?", "a": "No. I produce drafts for your review and approval. Actual sending requires a WhatsApp Business integration, which is out of scope for this build.", "category": "Capabilities"},
    {"q": "Can you write in Hindi or other languages?", "a": "Yes. Add 'in Hindi' (or Marathi, Tamil, etc.) and I'll write the whole message in that language. English is the default.", "category": "Capabilities"},
    {"q": "Can you handle multiple products at once?", "a": "I focus a run on one target product for clarity. Ask a follow-up for a different product and I'll re-run.", "category": "Capabilities"},
    {"q": "Can you compare two products for a customer?", "a": "I recommend the single best-fit product per customer by propensity. Side-by-side product comparison is on the roadmap.", "category": "Capabilities"},
    {"q": "How many customers do you return?", "a": "The top 10 by combined value + propensity, by default. Ask 'top 5' or 'top 20' to change it.", "category": "Capabilities"},

    # Products
    {"q": "Which products can you recommend?", "a": "Personal Loan, Home Loan, Personal Overdraft, Privilege Credit Card, Cashback Credit Card, Equity SIP, and Fixed Deposit.", "category": "Products"},
    {"q": "Which product is best for salary-slowdown customers?", "a": "Typically a Personal Overdraft (liquidity buffer) or consolidation — I weight propensity over wallet size for these retention cases.", "category": "Products"},
    {"q": "What suits a customer with idle savings?", "a": "An Equity SIP or Fixed Deposit, depending on risk appetite — I check eligibility and surface the better-fit option.", "category": "Products"},
    {"q": "Who should get a premium credit card?", "a": "Customers with high premium-merchant spend, strong UPI velocity, income above the threshold, and no existing card.", "category": "Products"},
    {"q": "How do you check eligibility?", "a": "Each product has rules (min income, age band, KYC, risk appetite). I filter candidates against them before recommending.", "category": "Products"},

    # Scoring
    {"q": "How is the value score calculated?", "a": "A transparent weighted model over average balance, monthly income, account tenure, and transaction velocity — z-scored against the candidate pool.", "category": "Scoring"},
    {"q": "What is the propensity score?", "a": "A per-product likelihood (0–100%) to convert, from product-specific behavioural signals, with the top driving features shown.", "category": "Scoring"},
    {"q": "What is the composite score?", "a": "A blend of value and propensity. For acquisition it's 40% value / 60% propensity; for retention products propensity dominates (80%).", "category": "Scoring"},
    {"q": "Why was a customer ranked highly?", "a": "Open their card — I show the top contributing features (e.g. recent large debit, salary growth, idle surplus) with their weights.", "category": "Scoring"},
    {"q": "Is the scoring a black box?", "a": "No. Weights live in a config file and every recommendation lists its top features — built for BFSI auditability.", "category": "Scoring"},
    {"q": "Do you use a trained ML model?", "a": "This build uses transparent weighted/heuristic models for explainability. A trained model can be added behind the same interface.", "category": "Scoring"},

    # Data
    {"q": "What data do you use?", "a": "Customer profiles, accounts/balances, transactions, product holdings, and past interaction notes.", "category": "Data"},
    {"q": "Where does the data live?", "a": "Primary source is a Databricks Delta warehouse with an automatic SQLite fallback. Every result shows which source served it.", "category": "Data"},
    {"q": "Is this real customer data?", "a": "No — it's synthetic demo data (≈500 customers plus a few hand-crafted personas). No real PII.", "category": "Data"},
    {"q": "How fresh is the data?", "a": "In this build it's seeded at startup. A production deployment would read live warehouse tables.", "category": "Data"},
    {"q": "Can I see a customer's full profile?", "a": "Yes — click any candidate to open Customer 360: profile, holdings, recent transactions, interaction notes, score breakdown, and the draft.", "category": "Data"},

    # Compliance / trust
    {"q": "Will the messages contain wrong numbers?", "a": "No. A numeric-grounding validator strips any number not present in the customer's real data — no fabricated rates or EMIs.", "category": "Compliance"},
    {"q": "What does the 'compliance ok' badge mean?", "a": "It confirms every number in the draft is grounded in source data. If something was stripped, you'll see a 'redacted' note.", "category": "Compliance"},
    {"q": "Can I edit a draft before approving?", "a": "Yes — edit inline in the WhatsApp preview, then Approve & queue.", "category": "Compliance"},
    {"q": "Is there an audit trail?", "a": "Yes — every agent step is saved and replayable per session, suitable for compliance review.", "category": "Compliance"},
    {"q": "Do you make credit decisions?", "a": "No. I surface opportunities and draft outreach. Underwriting and credit decisions stay with the bank's systems and officers.", "category": "Compliance"},

    # Sentiment / retention
    {"q": "What is the churn-risk flag?", "a": "I scan interaction notes for negative sentiment and churn signals (e.g. 'EMI stress', 'switch banks') and flag those customers for priority retention attention.", "category": "Retention"},
    {"q": "How do you detect sentiment?", "a": "A rule-based analysis over interaction notes labels each customer positive, neutral, or negative, with an escalation flag for churn risk.", "category": "Retention"},
    {"q": "What should I do with an escalated customer?", "a": "Prioritise a personal call and consider a defensive offer (overdraft, restructuring) rather than a hard product pitch.", "category": "Retention"},

    # Workflow / UI
    {"q": "What is the 'Agent reasoning' panel?", "a": "It streams my live plan, each tool call, the critic's checks, and the synthesis — collapsed by default; click 'Show' to expand.", "category": "Using the app"},
    {"q": "What's in the right-hand panel?", "a": "The ranked candidates. Click one for full details and its WhatsApp draft.", "category": "Using the app"},
    {"q": "How do I start a fresh topic?", "a": "Click 'New conversation' in the left sidebar. Past sessions are listed there too.", "category": "Using the app"},
    {"q": "Can I continue an old conversation?", "a": "Yes — pick it from the sidebar; follow-ups use that session's context.", "category": "Using the app"},
    {"q": "Why did I get no candidates?", "a": "The filters were too tight or no one matched. Try a different city, a lower balance threshold, or a broader segment.", "category": "Using the app"},
    {"q": "What do the score colours mean?", "a": "Green ≥75 (strong), blue 55–74 (good), amber below 55 (marginal) — for the composite score ring.", "category": "Using the app"},
    {"q": "Can I export the list?", "a": "Export to CSV/XLSX is on the roadmap; for now you can approve drafts and review them per session.", "category": "Using the app"},

    # Scope / meta
    {"q": "Who are you?", "a": "I'm RM Copilot, an AI assistant for a retail-banking Relationship Manager — focused on customer targeting and outreach.", "category": "About"},
    {"q": "Can you answer general questions?", "a": "I stay within banking CRM. For anything else I'll point you back to what I do best: finding customers and drafting outreach.", "category": "About"},
    {"q": "What can't you do?", "a": "Send messages, make credit decisions, give legal/regulatory advice, or work outside retail-banking CRM.", "category": "About"},
    {"q": "Which LLMs power you?", "a": "Reasoning runs on Gemini; high-volume drafting on Groq Llama 3.3; with a deterministic offline fallback. Embeddings use Gemini.", "category": "About"},
    {"q": "How does RAG work here?", "a": "Hybrid retrieval over interaction notes — dense embeddings plus BM25, fused and diversity-re-ranked, with citations.", "category": "About"},
    {"q": "Is my conversation saved?", "a": "Yes, per session, so you can revisit it and so follow-ups have context. It's single-RM demo storage.", "category": "About"},
    {"q": "How fast are you?", "a": "A full run typically completes in a few seconds; the plan streams within about a second.", "category": "About"},
    {"q": "What happens if the warehouse is down?", "a": "I automatically fall back to a local copy, so the demo never breaks — the trace shows 'sqlite(failover)'.", "category": "About"},
    {"q": "Can you handle a different RM or bank?", "a": "The design is multi-tenant-ready; this build is configured for RM Rohan with synthetic data.", "category": "About"},
]


def faq_knowledge_text() -> str:
    """Compact grounding text for the FAQ node."""
    lines = [
        f"DOMAIN: {DOMAIN['name']} — {DOMAIN['scope']}",
        f"OUT OF SCOPE: {DOMAIN['out_of_scope']}",
        "",
        "PRODUCTS: " + ", ".join(p["name"] for p in PRODUCTS),
        "",
        "CAPABILITIES:",
    ]
    lines += [f"- {c['title']}: {c['desc']}" for c in CAPABILITIES]
    lines += ["", "FAQs:"]
    lines += [f"Q: {f['q']}\nA: {f['a']}" for f in FAQS]
    return "\n".join(lines)
