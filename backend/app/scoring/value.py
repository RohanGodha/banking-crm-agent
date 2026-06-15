"""Customer value scoring — transparent and explainable.

For each candidate we compute:
  value_score = sigmoid(weighted sum of z-scored features)

We return the score AND the feature contributions so the agent can quote them.
"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from app.domain import ScoreBreakdown

_WEIGHTS_PATH = Path(__file__).parent / "weights.yaml"
_WEIGHTS: dict[str, Any] = yaml.safe_load(_WEIGHTS_PATH.read_text(encoding="utf-8"))


def _months_between(iso_date: str) -> int:
    try:
        d = datetime.fromisoformat(iso_date)
    except Exception:  # noqa: BLE001
        return 0
    delta = datetime.utcnow() - d
    return max(int(delta.days / 30), 0)


def _zscore(value: float, population: list[float]) -> float:
    if not population:
        return 0.0
    arr = np.array(population, dtype=float)
    mu = float(arr.mean())
    sigma = float(arr.std()) or 1.0
    return (value - mu) / sigma


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def compute_value(
    customer: dict[str, Any],
    population: list[dict[str, Any]],
    txn_count_6m: int = 0,
) -> tuple[float, list[ScoreBreakdown]]:
    """Return (value_score in [0,1], list of feature contributions)."""
    w = _WEIGHTS["value"]

    balances = [float(c.get("avg_balance_6m") or c.get("balance") or 0) for c in population]
    incomes = [float(c.get("monthly_income") or 0) for c in population]
    tenures = [float(_months_between(c.get("account_open_date", ""))) for c in population]
    velocities = [float(c.get("_txn_velocity") or 0) for c in population]

    balance = float(customer.get("avg_balance_6m") or customer.get("balance") or 0)
    income = float(customer.get("monthly_income") or 0)
    tenure = float(_months_between(customer.get("account_open_date", "")))
    velocity = float(txn_count_6m)

    bz = _zscore(balance, balances)
    iz = _zscore(income, incomes)
    tz = _zscore(tenure, tenures)
    vz = _zscore(velocity, velocities)

    contribs = [
        ("balance_z", bz, w["balance_z"], "Average 6-month balance vs portfolio."),
        ("income_z", iz, w["income_z"], "Monthly income vs portfolio."),
        ("tenure_z", tz, w["tenure_z"], "Account tenure vs portfolio."),
        ("txn_velocity_z", vz, w["txn_velocity_z"], "Transaction velocity (count, 6m) vs portfolio."),
    ]

    raw = sum(weight * z for (_, z, weight, _) in contribs)
    score = _sigmoid(raw)

    breakdowns = [
        ScoreBreakdown(
            feature=name,
            value=round(z, 3),
            contribution=round(z * weight, 3),
            direction=("positive" if z * weight > 0.02 else ("negative" if z * weight < -0.02 else "neutral")),
            rationale=rationale,
        )
        for (name, z, weight, rationale) in contribs
    ]
    return round(score, 4), breakdowns
