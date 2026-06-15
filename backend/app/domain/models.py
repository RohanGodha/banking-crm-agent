"""Pydantic domain models. Tools and API responses use these directly."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    age: int
    city: str
    segment: Literal["mass", "mass_affluent", "affluent", "hnw"]
    employment: str
    monthly_income: float
    account_open_date: str
    kyc_status: str = "verified"
    phone: str
    email: str | None = None
    risk_appetite: str = "medium"

    # Enriched fields (joined from accounts)
    balance: float | None = None
    avg_balance_6m: float | None = None


class Transaction(BaseModel):
    id: str
    customer_id: str
    ts: str
    amount: float
    category: str
    channel: str
    merchant: str | None = None


class Product(BaseModel):
    id: str
    name: str
    category: str
    interest_rate: float | None = None
    min_income: float | None = None
    min_age: int | None = None
    max_age: int | None = None
    description: str | None = None
    eligibility: dict[str, Any] = Field(default_factory=dict)


class CustomerFilters(BaseModel):
    """Used by `query_customers` tool. All optional, all AND-combined."""
    cities: list[str] | None = None
    segments: list[str] | None = None
    employment: list[str] | None = None
    min_income: float | None = None
    max_income: float | None = None
    min_balance: float | None = None
    min_age: int | None = None
    max_age: int | None = None
    risk_appetite: list[str] | None = None
    exclude_products: list[str] | None = None
    limit: int = 200


class ScoreBreakdown(BaseModel):
    """Explainable contribution of a single feature to a score."""
    feature: str
    value: float
    contribution: float
    direction: Literal["positive", "negative", "neutral"] = "neutral"
    rationale: str


class Candidate(BaseModel):
    """A customer + scoring + recommendation, ready for the UI."""
    customer: Customer
    value_score: float = 0.0
    propensity_score: float = 0.0
    composite_score: float = 0.0
    recommended_product_id: str | None = None
    recommended_product_name: str | None = None
    feature_contributions: list[ScoreBreakdown] = Field(default_factory=list)
    rationale: str = ""
    citations: list[str] = Field(default_factory=list)


class OutreachDraft(BaseModel):
    id: str
    session_id: str
    customer_id: str
    product_id: str
    channel: str = "whatsapp"
    message: str
    score: float | None = None
    compliance: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
