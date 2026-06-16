"""Sentiment + churn-risk analysis over a customer's interaction notes.

Adapted from the VFS RAG bot's sentiment/escalation pattern, but fitted to a
banking RM context: instead of routing an angry *customer* to a live agent, we
score each *candidate's* recent interaction notes and flag negative-sentiment /
churn-risk customers for priority human attention (retention escalation).

Deterministic + rule-based so it runs offline and fast (no LLM needed). When a
real LLM is configured the synthesizer can optionally refine it, but the rules
already capture the high-signal cues present in banking notes.
"""
from __future__ import annotations

from typing import Any, Literal

Sentiment = Literal["positive", "neutral", "negative"]

_NEGATIVE = {
    "stress", "tight", "tightness", "shortfall", "miss", "missed", "delay", "delayed",
    "unhappy", "frustrated", "complaint", "complain", "dissatisfied", "angry", "issue",
    "problem", "difficult", "difficulties", "concern", "concerned", "worried", "struggle",
    "emi stress", "cash-flow", "cashflow", "grace period", "restructuring", "default",
    "penalty", "failed", "failure", "escalate", "cancel", "close account", "switch",
}
_POSITIVE = {
    "happy", "satisfied", "great", "excellent", "interested", "keen", "love",
    "appreciate", "thanks", "thank you", "pleased", "excited", "smooth", "helpful",
}
_CHURN = {
    "close account", "switch", "cancel", "leave", "competitor", "another bank",
    "moving to", "shut", "withdraw everything", "transfer out",
}


def analyze_sentiment(interactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return {sentiment, score, escalate, churn_risk, signals[]}."""
    if not interactions:
        return {"sentiment": "neutral", "score": 0.0, "escalate": False, "churn_risk": False, "signals": []}

    text = " ".join((i.get("summary") or "").lower() for i in interactions)
    signals: list[str] = []

    neg = sum(1 for kw in _NEGATIVE if kw in text)
    pos = sum(1 for kw in _POSITIVE if kw in text)
    churn = [kw for kw in _CHURN if kw in text]

    for kw in _NEGATIVE:
        if kw in text:
            signals.append(kw)

    # Net score in [-1, 1]
    total = neg + pos
    score = 0.0 if total == 0 else round((pos - neg) / total, 3)

    sentiment: Sentiment = "neutral"
    if score <= -0.34 or neg >= 2:
        sentiment = "negative"
    elif score >= 0.34 and neg == 0:
        sentiment = "positive"

    churn_risk = len(churn) > 0 or neg >= 3
    escalate = sentiment == "negative" or churn_risk

    return {
        "sentiment": sentiment,
        "score": score,
        "escalate": escalate,
        "churn_risk": churn_risk,
        "signals": signals[:5],
    }
