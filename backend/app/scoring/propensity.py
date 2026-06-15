"""Per-product propensity scoring.

Logistic combination of product-specific features. All features in [-1, 1] roughly.
Returns (score in [0,1], list of ScoreBreakdown) so the agent has an audit trail.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from app.domain import ScoreBreakdown

_WEIGHTS_PATH = Path(__file__).parent / "weights.yaml"
_WEIGHTS: dict[str, Any] = yaml.safe_load(_WEIGHTS_PATH.read_text(encoding="utf-8"))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _norm(x: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.0
    return max(min((x - lo) / (hi - lo), 1.0), 0.0)


# ---------------------------------------------------------------------------
# Feature builders. Each returns float in roughly [-1, 1] (some only [0, 1]).
# ---------------------------------------------------------------------------

def _salary_credits(txns: list[dict[str, Any]]) -> list[tuple[str, float]]:
    return [
        (t.get("ts", ""), float(t["amount"]))
        for t in txns
        if t.get("category") == "salary" and float(t["amount"]) > 0
    ]


def _salary_trend(txns: list[dict[str, Any]]) -> float:
    """+1 means growing, -1 means falling, 0 flat."""
    sal = sorted(_salary_credits(txns))
    if len(sal) < 4:
        return 0.0
    recent = sum(a for _, a in sal[-3:]) / 3
    older = sum(a for _, a in sal[:-3]) / max(len(sal) - 3, 1)
    if older == 0:
        return 0.0
    delta = (recent - older) / older
    return max(min(delta * 2.0, 1.0), -1.0)


def _salary_dropping(txns: list[dict[str, Any]]) -> float:
    return max(-_salary_trend(txns), 0.0)


def _recent_large_debit(txns: list[dict[str, Any]], days: int = 60) -> float:
    debits = [abs(float(t["amount"])) for t in txns
              if float(t["amount"]) < 0 and t.get("category") in {"travel", "shopping", "other"}]
    if not debits:
        return 0.0
    top = max(debits)
    return _norm(top, 25000, 250000)  # ₹25k → ₹2.5L


def _emi_to_income(txns: list[dict[str, Any]], income: float) -> float:
    if income <= 0:
        return 0.0
    emis = [abs(float(t["amount"])) for t in txns if t.get("category") == "emi"]
    if not emis:
        return 0.0
    monthly_emi = sum(emis) / 3.0  # rough 3-month average
    return min(monthly_emi / income, 1.0)


def _has_product(holdings: list[dict[str, Any]], category: str | None = None, product_id: str | None = None) -> bool:
    for h in holdings:
        if product_id and h.get("product_id") == product_id:
            return True
        if category and h.get("category") == category:
            return True
    return False


def _premium_merchant_spend(txns: list[dict[str, Any]]) -> float:
    PREMIUM = {"apple", "starbucks", "indigo", "uber premier", "ola prime",
               "taj", "decathlon", "nykaa", "croma", "amazon"}
    score = 0.0
    for t in txns:
        m = (t.get("merchant") or "").lower()
        if any(p in m for p in PREMIUM):
            score += 1
    return _norm(score, 0, 8)


def _upi_velocity(txns: list[dict[str, Any]]) -> float:
    upi_count = sum(1 for t in txns if t.get("channel") == "upi")
    return _norm(upi_count, 0, 40)


def _interaction_stress(interactions: list[dict[str, Any]]) -> float:
    keywords = ["stress", "emi", "miss", "tight", "shortfall", "grace", "restructuring", "overdraft"]
    for it in interactions:
        s = (it.get("summary") or "").lower()
        if any(k in s for k in keywords):
            return 1.0
    return 0.0


def _idle_surplus(customer: dict[str, Any]) -> float:
    bal = float(customer.get("avg_balance_6m") or customer.get("balance") or 0)
    inc = float(customer.get("monthly_income") or 0)
    if inc <= 0:
        return 0.0
    ratio = bal / inc
    return _norm(ratio, 2, 12)  # >12x income idle = max surplus signal


def _age_band(customer: dict[str, Any], lo: int, hi: int) -> float:
    age = int(customer.get("age") or 0)
    if lo <= age <= hi:
        center = (lo + hi) / 2
        width = (hi - lo) / 2 or 1
        return 1.0 - abs(age - center) / width
    return 0.0


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def predict_propensity(
    customer: dict[str, Any],
    txns: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    product_id: str,
) -> tuple[float, list[ScoreBreakdown]]:
    """Return (propensity in [0,1], explainable breakdown)."""
    weights = _WEIGHTS["propensity"].get(product_id)
    if weights is None:
        return 0.0, []

    income = float(customer.get("monthly_income") or 0)
    f: dict[str, float] = {}

    f["salary_credit_trend"] = _salary_trend(txns)
    f["salary_credit_dropping"] = _salary_dropping(txns)
    f["recent_large_debit_signal"] = _recent_large_debit(txns)
    f["emi_to_income_ratio"] = _emi_to_income(txns, income)
    f["existing_emi_present"] = 1.0 if any(t.get("category") == "emi" for t in txns) else 0.0
    f["no_existing_loan_bonus"] = 0.0 if _has_product(holdings, category="loan") else 1.0
    f["no_home_loan"] = 0.0 if _has_product(holdings, product_id="PROD-LOAN-HL") else 1.0
    f["no_card_held"] = 0.0 if _has_product(holdings, category="card") else 1.0
    f["no_mf_holding"] = 0.0 if _has_product(holdings, category="investment") else 1.0
    f["balance_buffer"] = _idle_surplus(customer)
    f["balance_buffer_low"] = 1.0 - _idle_surplus(customer)
    f["tenure_long"] = _norm(_months_between_safe(customer.get("account_open_date", "")), 12, 120)
    f["age_band_fit"] = _age_band(customer, 23, 55)
    f["age_under_45"] = 1.0 if int(customer.get("age") or 0) < 45 else 0.0
    f["income_above_25k"] = 1.0 if income >= 25000 else 0.0
    f["income_above_50k"] = 1.0 if income >= 50000 else 0.0
    f["income_above_75k"] = 1.0 if income >= 75000 else 0.0
    f["premium_merchant_spend"] = _premium_merchant_spend(txns)
    f["upi_velocity"] = _upi_velocity(txns)
    f["interaction_stress_signal"] = _interaction_stress(interactions)
    f["risk_appetite_med_high"] = 1.0 if (customer.get("risk_appetite") in ("medium", "high")) else 0.0
    f["idle_surplus"] = _idle_surplus(customer)

    breakdowns: list[ScoreBreakdown] = []
    raw = 0.0
    for feat_name, weight in weights.items():
        value = f.get(feat_name, 0.0)
        contribution = weight * value
        raw += contribution
        direction = "positive" if contribution > 0.02 else ("negative" if contribution < -0.02 else "neutral")
        breakdowns.append(
            ScoreBreakdown(
                feature=feat_name,
                value=round(value, 3),
                contribution=round(contribution, 3),
                direction=direction,
                rationale=_RATIONALES.get(feat_name, ""),
            )
        )
    score = _sigmoid(raw * 2.5)  # scale to widen the curve
    return round(score, 4), sorted(breakdowns, key=lambda b: abs(b.contribution), reverse=True)


def _months_between_safe(iso: str) -> int:
    from datetime import datetime

    try:
        return max(int((datetime.utcnow() - datetime.fromisoformat(iso)).days / 30), 0)
    except Exception:  # noqa: BLE001
        return 0


_RATIONALES: dict[str, str] = {
    "salary_credit_trend": "Trend in salary credits over recent months.",
    "salary_credit_dropping": "Detected dip in salary credits — possible cash-flow stress.",
    "recent_large_debit_signal": "Large discretionary debit (travel/shopping) — possible upcoming financing need.",
    "emi_to_income_ratio": "Existing EMI burden relative to income (higher = worse).",
    "existing_emi_present": "Whether the customer is currently servicing an EMI.",
    "no_existing_loan_bonus": "No active loan — bank wallet share opportunity.",
    "no_home_loan": "No active home loan with us.",
    "no_card_held": "No credit card held — wallet share opportunity.",
    "no_mf_holding": "No mutual-fund holding — cross-sell opportunity.",
    "balance_buffer": "Healthy savings buffer relative to income.",
    "balance_buffer_low": "Buffer is thin — supports overdraft / liquidity products.",
    "tenure_long": "Long-standing customer — higher trust.",
    "age_band_fit": "Within product's optimal age band.",
    "age_under_45": "Younger profile — higher cross-sell elasticity.",
    "income_above_25k": "Income clears the entry-level eligibility threshold.",
    "income_above_50k": "Income clears the mid-tier eligibility threshold.",
    "income_above_75k": "Income clears the premium eligibility threshold.",
    "premium_merchant_spend": "Premium-merchant spend pattern indicates affinity for premium products.",
    "upi_velocity": "High UPI velocity — high active engagement.",
    "interaction_stress_signal": "Past interaction notes mention financial stress.",
    "risk_appetite_med_high": "Self-reported risk appetite supports market-linked products.",
    "idle_surplus": "Surplus parked idle — opportunity for investment cross-sell.",
}
