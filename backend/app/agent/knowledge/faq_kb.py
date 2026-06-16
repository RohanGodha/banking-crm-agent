"""Grounded knowledge base for the FAQ handler.

Kept small and factual. The FAQ node feeds this verbatim to the LLM and forbids
answering beyond it — so capability answers stay accurate and never hallucinate
features we don't have.
"""
from __future__ import annotations

FAQ_KNOWLEDGE_BASE = """\
ABOUT RM COPILOT
- RM Copilot is an agentic AI assistant for a retail-banking Relationship Manager (RM).
- It finds high-value customers, scores their likelihood to convert for a product,
  recommends suitable products, and drafts compliance-checked WhatsApp outreach.
- It shows its full reasoning step-by-step (plan -> tools -> critic -> synthesis) and
  lists ranked candidates with an editable draft for each.

WHAT IT CAN DO
- "Find / show / list" customers by city, segment, income, balance, age, risk appetite.
- Score customer VALUE (balance, income, tenure, transaction velocity).
- Predict PROPENSITY to convert for a specific product, with explainable top features.
- Recommend the best-fit product per customer (eligibility-checked).
- Draft a personalised WhatsApp message per customer, grounded in real signals.
- Refine results conversationally ("now only Bangalore", "make it warmer", "top 5").

PRODUCTS IT CAN TARGET
- Personal Loan, Home Loan, Personal Overdraft, Privilege Credit Card,
  Cashback Credit Card, Equity SIP, Fixed Deposit.

DATA IT USES
- Customer profiles, accounts/balances, transactions, product holdings, and past
  interaction notes. In this build the data is synthetic (for demo). The primary data
  source is a Databricks Delta warehouse with an automatic SQLite fallback.

HOW SCORING WORKS
- Transparent, explainable weighted models (not a black box). Each recommendation shows
  the top contributing features so the RM understands the "why".

COMPLIANCE
- Every drafted message passes a numeric-grounding validator: any number not present in
  the customer's real data is stripped. No fabricated rates or EMIs.

WHAT IT CANNOT DO (yet)
- It does NOT actually send WhatsApp messages — it produces drafts for RM review/approval.
- It is single-RM (Rohan) and uses synthetic demo data.
- It does not give regulatory/legal advice or make final credit decisions.
"""
