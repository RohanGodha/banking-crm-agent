"""End-to-end seeder: products, hero customers + 495 Faker customers + transactions + interactions.

Idempotent. Designed so the scorer's hero customers actually rank top.
"""
from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from faker import Faker

from app.observability import get_logger

from .hero_customers import HeroCustomer, days_ago, hero_customers

logger = get_logger(__name__)

INDIAN_CITIES = [
    "Mumbai", "Bangalore", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata",
    "Ahmedabad", "Jaipur", "Lucknow", "Indore", "Chandigarh", "Kochi", "Surat",
]
SEGMENTS = ["mass", "mass_affluent", "affluent", "hnw"]
EMPLOYMENT = ["salaried", "self_employed", "business"]
RISK = ["low", "medium", "high"]
TXN_CATEGORIES = ["salary", "upi", "emi", "travel", "shopping", "utility", "investment", "other"]
CHANNELS = ["upi", "neft", "card", "atm", "branch"]

NOISE_COUNT = 495


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def _seed_products(conn: sqlite3.Connection) -> None:
    products = [
        ("PROD-SAV-001", "Savings Account Plus", "savings", None, 0, 18, 80,
         "Premium savings with debit card and zero balance.",
         {"min_age": 18}),
        ("PROD-LOAN-PL", "Personal Loan", "loan", 11.5, 25000, 23, 60,
         "Unsecured personal loan up to ₹40L, 12-60 month tenure.",
         {"min_age": 23, "max_age": 60, "min_income": 25000, "kyc": "verified"}),
        ("PROD-LOAN-HL", "Home Loan", "loan", 8.6, 30000, 21, 65,
         "Home loan up to 90% of property value, tenure up to 30 years.",
         {"min_age": 21, "max_age": 65, "min_income": 30000}),
        ("PROD-LOAN-OD", "Personal Overdraft", "overdraft", 13.5, 20000, 21, 60,
         "Pre-approved overdraft up to 5x monthly salary, interest only on used amount.",
         {"min_age": 21, "max_age": 60, "min_income": 20000, "salary_account": True}),
        ("PROD-CARD-PREM", "Privilege Credit Card", "card", 36.0, 75000, 21, 65,
         "Premium credit card with airport lounge access, milestone rewards, and 5x points on travel.",
         {"min_age": 21, "max_age": 65, "min_income": 75000}),
        ("PROD-CARD-CB", "Cashback Credit Card", "card", 36.0, 25000, 21, 65,
         "Everyday cashback credit card — 5% on groceries and utilities.",
         {"min_age": 21, "max_age": 65, "min_income": 25000}),
        ("PROD-INV-SIP", "Equity SIP", "investment", None, 5000, 18, 70,
         "Systematic Investment Plan in diversified equity mutual funds.",
         {"min_age": 18, "max_age": 70, "risk_appetite": ["medium", "high"]}),
        ("PROD-INV-FD", "Fixed Deposit", "investment", 7.1, 1000, 18, 100,
         "Fixed deposit with quarterly interest payout.",
         {"min_age": 18}),
    ]
    rows = [
        (pid, name, cat, rate, min_inc, min_age, max_age, desc, json.dumps(elig))
        for (pid, name, cat, rate, min_inc, min_age, max_age, desc, elig) in products
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO products
            (id, name, category, interest_rate, min_income, min_age, max_age, description, eligibility_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# Hero customers
# ---------------------------------------------------------------------------

def _insert_hero(conn: sqlite3.Connection, h: HeroCustomer) -> None:
    open_date = (date.today() - timedelta(days=365 * h.account_open_years_ago)).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO customers
        (id, name, age, city, segment, employment, monthly_income, account_open_date,
         kyc_status, phone, email, risk_appetite)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?, ?)
        """,
        (h.id, h.name, h.age, h.city, h.segment, h.employment, h.monthly_income,
         open_date, h.phone, h.email, h.risk_appetite),
    )
    account_id = f"ACC-{h.id[-3:]}"
    conn.execute(
        """
        INSERT OR REPLACE INTO accounts (id, customer_id, type, balance, avg_balance_6m, opened_at)
        VALUES (?, ?, 'salary', ?, ?, ?)
        """,
        (account_id, h.id, h.balance, h.avg_balance_6m, open_date),
    )
    for t in h.txns:
        ts = (datetime.utcnow() - timedelta(days=t.days_ago)).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO transactions (id, customer_id, ts, amount, category, channel, merchant)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), h.id, ts, t.amount, t.category, t.channel, t.merchant),
        )
    for inter in h.interactions:
        conn.execute(
            """
            INSERT INTO interactions (id, customer_id, ts, channel, summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), h.id, days_ago(inter.days_ago), inter.channel, inter.summary),
        )
    for pid in h.existing_products:
        conn.execute(
            """
            INSERT OR IGNORE INTO holdings (customer_id, product_id, opened_at, status)
            VALUES (?, ?, ?, 'active')
            """,
            (h.id, pid, open_date),
        )


# ---------------------------------------------------------------------------
# Faker noise customers
# ---------------------------------------------------------------------------

def _seed_noise(conn: sqlite3.Connection, count: int = NOISE_COUNT) -> None:
    fake = Faker("en_IN")
    Faker.seed(7)
    random.seed(7)

    for i in range(count):
        cid = f"CUST-{i + 1:05d}"
        segment = random.choices(SEGMENTS, weights=[0.45, 0.30, 0.18, 0.07])[0]
        income_range = {
            "mass": (20000, 45000),
            "mass_affluent": (45000, 100000),
            "affluent": (100000, 200000),
            "hnw": (200000, 500000),
        }[segment]
        income = round(random.uniform(*income_range), -2)
        balance_multiplier = {
            "mass": (0.5, 2.0),
            "mass_affluent": (1.5, 4.0),
            "affluent": (3.0, 8.0),
            "hnw": (5.0, 12.0),
        }[segment]
        balance = round(income * random.uniform(*balance_multiplier), -3)
        avg_bal = round(balance * random.uniform(0.85, 1.15), -3)
        age = random.randint(22, 62)
        years_open = random.randint(1, 12)
        open_date = (date.today() - timedelta(days=365 * years_open + random.randint(0, 364))).isoformat()

        conn.execute(
            """
            INSERT INTO customers
            (id, name, age, city, segment, employment, monthly_income, account_open_date,
             kyc_status, phone, email, risk_appetite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?, ?)
            """,
            (cid, fake.name(), age, random.choice(INDIAN_CITIES), segment,
             random.choice(EMPLOYMENT), income, open_date,
             f"+91-{random.randint(70000, 99999)}-{random.randint(10000, 99999)}",
             fake.email(), random.choice(RISK)),
        )

        conn.execute(
            """
            INSERT INTO accounts (id, customer_id, type, balance, avg_balance_6m, opened_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"ACC-{i + 1:05d}", cid, random.choice(["savings", "salary"]),
             balance, avg_bal, open_date),
        )

        # transactions: 3-6 salary credits + 8-25 misc
        n_salary = random.randint(3, 6)
        for k in range(n_salary):
            ts = (datetime.utcnow() - timedelta(days=30 * k + random.randint(0, 3))).isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO transactions (id, customer_id, ts, amount, category, channel, merchant) VALUES (?, ?, ?, ?, 'salary', 'neft', ?)",
                (str(uuid.uuid4()), cid, ts, income, fake.company()),
            )
        n_misc = random.randint(8, 25)
        for _ in range(n_misc):
            cat = random.choices(
                ["upi", "emi", "travel", "shopping", "utility", "investment", "other"],
                weights=[0.30, 0.10, 0.10, 0.20, 0.15, 0.05, 0.10],
            )[0]
            amt = -round(random.uniform(200, income * 0.4), 0)
            ts = (datetime.utcnow() - timedelta(days=random.randint(1, 180))).isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO transactions (id, customer_id, ts, amount, category, channel, merchant) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), cid, ts, amt, cat, random.choice(CHANNELS), fake.company()),
            )

        # ~25% have one interaction note
        if random.random() < 0.25:
            templates = [
                "Customer enquired about FD rates during routine call.",
                "Discussed loan refinancing options — customer wants to compare.",
                "Customer was unhappy about a failed transaction — issue resolved.",
                "Branch visit for KYC re-verification, all clear.",
                "Asked about credit card upgrade options.",
            ]
            conn.execute(
                "INSERT INTO interactions (id, customer_id, ts, channel, summary) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), cid, days_ago(random.randint(5, 90)),
                 random.choice(["call", "branch", "email"]), random.choice(templates)),
            )

        # ~35% hold at least the savings + maybe 1 other
        conn.execute(
            "INSERT OR IGNORE INTO holdings (customer_id, product_id, opened_at, status) VALUES (?, ?, ?, 'active')",
            (cid, "PROD-SAV-001", open_date),
        )
        if random.random() < 0.35:
            other = random.choice(["PROD-CARD-CB", "PROD-INV-FD", "PROD-LOAN-HL"])
            conn.execute(
                "INSERT OR IGNORE INTO holdings (customer_id, product_id, opened_at, status) VALUES (?, ?, ?, 'active')",
                (cid, other, open_date),
            )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run_seed(conn: sqlite3.Connection) -> None:
    logger.info("Seeding products...")
    _seed_products(conn)
    logger.info("Seeding hero customers...")
    for h in hero_customers():
        _insert_hero(conn, h)
    logger.info("Seeding %d Faker noise customers...", NOISE_COUNT)
    _seed_noise(conn, NOISE_COUNT)
    conn.commit()
    logger.info("Seed complete.")


if __name__ == "__main__":
    from app.db.sqlite_engine import bootstrap

    bootstrap()
