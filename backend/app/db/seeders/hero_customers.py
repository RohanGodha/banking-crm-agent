"""Hand-crafted hero customer personas used in the demo scenarios.

These customers are designed so the scoring engine ranks them naturally — not by
hardcoding — for their respective products. Their transaction patterns,
balances and interaction notes carry the signals the scorer is tuned for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal


@dataclass
class HeroTxn:
    days_ago: int
    amount: float
    category: str
    channel: str = "upi"
    merchant: str | None = None


@dataclass
class HeroInteraction:
    days_ago: int
    channel: str
    summary: str


@dataclass
class HeroCustomer:
    id: str
    name: str
    age: int
    city: str
    segment: Literal["mass", "mass_affluent", "affluent", "hnw"]
    employment: str
    monthly_income: float
    phone: str
    email: str
    account_open_years_ago: int
    balance: float
    avg_balance_6m: float
    risk_appetite: str = "medium"
    txns: list[HeroTxn] = field(default_factory=list)
    interactions: list[HeroInteraction] = field(default_factory=list)
    existing_products: list[str] = field(default_factory=list)
    expected_product: str = ""
    persona_note: str = ""


def hero_customers() -> list[HeroCustomer]:
    return [
        # ---------------------------------------------------------------
        # 1. PRIYA SHARMA — HNW Mumbai, prime Personal Loan candidate
        # ---------------------------------------------------------------
        HeroCustomer(
            id="CUST-HERO-001",
            name="Priya Sharma",
            age=34,
            city="Mumbai",
            segment="hnw",
            employment="salaried",
            monthly_income=320000,
            phone="+91-98200-11001",
            email="priya.sharma@example.in",
            account_open_years_ago=6,
            balance=5800000,
            avg_balance_6m=5200000,
            risk_appetite="medium",
            existing_products=["PROD-SAV-001"],
            expected_product="PROD-LOAN-PL",
            persona_note="HNW Mumbai, large recent travel debits, no existing loan — prime PL.",
            txns=[
                HeroTxn(3, 320000, "salary", "neft", "TechCorp Payroll"),
                HeroTxn(33, 320000, "salary", "neft", "TechCorp Payroll"),
                HeroTxn(63, 320000, "salary", "neft", "TechCorp Payroll"),
                HeroTxn(5, -185000, "travel", "card", "Makemytrip"),
                HeroTxn(12, -42000, "shopping", "card", "Apple Store"),
                HeroTxn(20, -28000, "travel", "card", "Taj Hotels"),
                HeroTxn(45, -32000, "shopping", "upi", "Tata CLiQ"),
                HeroTxn(8, -9500, "utility", "upi", "Tata Power"),
                HeroTxn(28, -9200, "utility", "upi", "Tata Power"),
            ],
            interactions=[
                HeroInteraction(
                    18,
                    "call",
                    "Priya mentioned planning a home renovation worth ~12-15 lakhs in the next "
                    "quarter and asked about financing options. Showed interest in unsecured "
                    "options to avoid pledging assets.",
                ),
                HeroInteraction(
                    62,
                    "branch",
                    "Visited Bandra branch for FD renewal. Casually asked about pre-approved "
                    "personal loan offers for premium customers.",
                ),
            ],
        ),
        # ---------------------------------------------------------------
        # 2. AARAV MEHTA — Affluent Bangalore, salary spike 23% YoY
        # ---------------------------------------------------------------
        HeroCustomer(
            id="CUST-HERO-002",
            name="Aarav Mehta",
            age=29,
            city="Bangalore",
            segment="affluent",
            employment="salaried",
            monthly_income=185000,
            phone="+91-98450-11002",
            email="aarav.mehta@example.in",
            account_open_years_ago=4,
            balance=2200000,
            avg_balance_6m=1850000,
            risk_appetite="high",
            existing_products=["PROD-SAV-001", "PROD-INV-SIP"],
            expected_product="PROD-LOAN-PL",
            persona_note="Salary credits up 23% YoY, recently opened SIP, low EMI burden.",
            txns=[
                HeroTxn(2, 185000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(32, 185000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(62, 185000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(95, 150000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(125, 150000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(155, 150000, "salary", "neft", "Flipkart Internet"),
                HeroTxn(5, -25000, "investment", "neft", "Zerodha SIP"),
                HeroTxn(35, -25000, "investment", "neft", "Zerodha SIP"),
                HeroTxn(10, -12000, "shopping", "card", "Decathlon"),
                HeroTxn(15, -8500, "travel", "upi", "Uber"),
            ],
            interactions=[
                HeroInteraction(
                    25,
                    "whatsapp",
                    "Aarav asked about pre-approved loan offers — said he wants to buy a car "
                    "but doesn't want a traditional auto loan with collateral.",
                ),
            ],
        ),
        # ---------------------------------------------------------------
        # 3. ANANYA IYER — Pune, salary-credit slowdown, retention
        # ---------------------------------------------------------------
        HeroCustomer(
            id="CUST-HERO-003",
            name="Ananya Iyer",
            age=38,
            city="Pune",
            segment="mass_affluent",
            employment="salaried",
            monthly_income=95000,
            phone="+91-98220-11003",
            email="ananya.iyer@example.in",
            account_open_years_ago=8,
            balance=210000,
            avg_balance_6m=340000,
            risk_appetite="low",
            existing_products=["PROD-SAV-001", "PROD-LOAN-HL"],
            expected_product="PROD-LOAN-OD",
            persona_note="Salary credits down ~18% last 2 months; mentioned EMI stress.",
            txns=[
                HeroTxn(3, 78000, "salary", "neft", "Persistent Systems"),
                HeroTxn(33, 78000, "salary", "neft", "Persistent Systems"),
                HeroTxn(63, 95000, "salary", "neft", "Persistent Systems"),
                HeroTxn(93, 95000, "salary", "neft", "Persistent Systems"),
                HeroTxn(123, 95000, "salary", "neft", "Persistent Systems"),
                HeroTxn(5, -35000, "emi", "neft", "Home Loan EMI"),
                HeroTxn(35, -35000, "emi", "neft", "Home Loan EMI"),
                HeroTxn(65, -35000, "emi", "neft", "Home Loan EMI"),
                HeroTxn(8, -18000, "utility", "upi", "MSEDCL"),
                HeroTxn(12, -7500, "shopping", "card", "BigBasket"),
            ],
            interactions=[
                HeroInteraction(
                    8,
                    "call",
                    "Ananya called RM expressing concern about cash-flow tightness — her "
                    "company moved her to a variable component and net credit dropped ~18%. "
                    "Asked if EMI restructuring or a short-term liquidity buffer is possible.",
                ),
                HeroInteraction(
                    40,
                    "whatsapp",
                    "Mentioned she might miss next month's EMI window by a few days; wanted "
                    "to know about overdraft or grace period.",
                ),
            ],
        ),
        # ---------------------------------------------------------------
        # 4. VIKRAM REDDY — Hyderabad, no credit card, premium merchant spends
        # ---------------------------------------------------------------
        HeroCustomer(
            id="CUST-HERO-004",
            name="Vikram Reddy",
            age=32,
            city="Hyderabad",
            segment="affluent",
            employment="salaried",
            monthly_income=140000,
            phone="+91-98480-11004",
            email="vikram.reddy@example.in",
            account_open_years_ago=3,
            balance=1450000,
            avg_balance_6m=1280000,
            risk_appetite="medium",
            existing_products=["PROD-SAV-001"],
            expected_product="PROD-CARD-PREM",
            persona_note="High UPI velocity, premium merchants, no credit card yet.",
            txns=[
                HeroTxn(1, 140000, "salary", "neft", "Microsoft IDC"),
                HeroTxn(31, 140000, "salary", "neft", "Microsoft IDC"),
                HeroTxn(61, 140000, "salary", "neft", "Microsoft IDC"),
                HeroTxn(2, -8500, "shopping", "upi", "Starbucks"),
                HeroTxn(4, -12000, "shopping", "upi", "Apple Store"),
                HeroTxn(6, -6500, "travel", "upi", "Uber Premier"),
                HeroTxn(9, -15000, "shopping", "upi", "Croma"),
                HeroTxn(11, -4200, "shopping", "upi", "Blue Tokai"),
                HeroTxn(14, -9800, "travel", "upi", "Indigo"),
                HeroTxn(18, -22000, "shopping", "upi", "Amazon"),
                HeroTxn(22, -5500, "shopping", "upi", "Starbucks"),
                HeroTxn(25, -7800, "travel", "upi", "Ola Prime"),
            ],
            interactions=[
                HeroInteraction(
                    14,
                    "email",
                    "Vikram replied to a newsletter and asked what premium credit cards the "
                    "bank offers — specifically interested in lounge access and milestone benefits.",
                ),
            ],
        ),
        # ---------------------------------------------------------------
        # 5. NEHA GUPTA — Delhi, HNW with idle surplus, no MF
        # ---------------------------------------------------------------
        HeroCustomer(
            id="CUST-HERO-005",
            name="Neha Gupta",
            age=34,
            city="Delhi",
            segment="hnw",
            employment="business",
            monthly_income=260000,
            phone="+91-98110-11005",
            email="neha.gupta@example.in",
            account_open_years_ago=5,
            balance=4100000,
            avg_balance_6m=3950000,
            risk_appetite="medium",
            existing_products=["PROD-SAV-001", "PROD-CARD-PREM"],
            expected_product="PROD-INV-SIP",
            persona_note="Idle surplus parked in savings, no MF, age 34 — SIP cross-sell.",
            txns=[
                HeroTxn(5, 260000, "salary", "neft", "Gupta Trading Co"),
                HeroTxn(35, 260000, "salary", "neft", "Gupta Trading Co"),
                HeroTxn(65, 260000, "salary", "neft", "Gupta Trading Co"),
                HeroTxn(95, 240000, "salary", "neft", "Gupta Trading Co"),
                HeroTxn(8, -45000, "shopping", "card", "Nykaa Luxe"),
                HeroTxn(20, -28000, "shopping", "card", "Westside"),
                HeroTxn(30, -12000, "utility", "upi", "Tata Power"),
                HeroTxn(50, -65000, "travel", "card", "Cleartrip"),
            ],
            interactions=[
                HeroInteraction(
                    22,
                    "branch",
                    "Neha asked how to make her idle savings work harder — said she's heard "
                    "about SIPs from a friend but never started one. Open to discussing.",
                ),
            ],
        ),
    ]


def today() -> date:
    return datetime.utcnow().date()


def days_ago(n: int) -> str:
    return (today() - timedelta(days=n)).isoformat()
