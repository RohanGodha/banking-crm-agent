"""SQLite adapter. Always available — also acts as the failover target."""
from __future__ import annotations

import json
import time
from typing import Any

from app.db.sqlite_engine import get_async_conn
from app.domain import Customer, CustomerFilters, Product, Transaction
from app.observability import get_logger

from .base import DataSource, DataSourceResult

logger = get_logger(__name__)


class SQLiteSource(DataSource):
    name = "sqlite"

    async def find_customers(self, filters: CustomerFilters) -> DataSourceResult:
        start = time.perf_counter()
        clauses: list[str] = []
        params: list[Any] = []
        if filters.cities:
            placeholders = ",".join(["?"] * len(filters.cities))
            clauses.append(f"c.city IN ({placeholders})")
            params.extend(filters.cities)
        if filters.segments:
            placeholders = ",".join(["?"] * len(filters.segments))
            clauses.append(f"c.segment IN ({placeholders})")
            params.extend(filters.segments)
        if filters.employment:
            placeholders = ",".join(["?"] * len(filters.employment))
            clauses.append(f"c.employment IN ({placeholders})")
            params.extend(filters.employment)
        if filters.min_income is not None:
            clauses.append("c.monthly_income >= ?")
            params.append(filters.min_income)
        if filters.max_income is not None:
            clauses.append("c.monthly_income <= ?")
            params.append(filters.max_income)
        if filters.min_balance is not None:
            clauses.append("a.balance >= ?")
            params.append(filters.min_balance)
        if filters.min_age is not None:
            clauses.append("c.age >= ?")
            params.append(filters.min_age)
        if filters.max_age is not None:
            clauses.append("c.age <= ?")
            params.append(filters.max_age)
        if filters.risk_appetite:
            placeholders = ",".join(["?"] * len(filters.risk_appetite))
            clauses.append(f"c.risk_appetite IN ({placeholders})")
            params.extend(filters.risk_appetite)
        if filters.exclude_products:
            placeholders = ",".join(["?"] * len(filters.exclude_products))
            clauses.append(
                f"c.id NOT IN (SELECT customer_id FROM holdings WHERE product_id IN ({placeholders}) AND status='active')"
            )
            params.extend(filters.exclude_products)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT c.*, a.balance, a.avg_balance_6m
            FROM customers c
            LEFT JOIN accounts a ON a.customer_id = c.id
            {where_sql}
            ORDER BY a.avg_balance_6m DESC
            LIMIT ?
        """
        params.append(int(filters.limit))

        async with get_async_conn() as conn:
            cur = await conn.execute(sql, params)
            rows = [dict(r) for r in await cur.fetchall()]

        customers = [Customer(**r).model_dump() for r in rows]
        elapsed = int((time.perf_counter() - start) * 1000)
        return DataSourceResult(source=self.name, latency_ms=elapsed, rows=len(customers), data=customers)

    async def get_customer(self, customer_id: str) -> DataSourceResult:
        start = time.perf_counter()
        async with get_async_conn() as conn:
            cur = await conn.execute(
                """
                SELECT c.*, a.balance, a.avg_balance_6m
                FROM customers c
                LEFT JOIN accounts a ON a.customer_id = c.id
                WHERE c.id = ?
                """,
                (customer_id,),
            )
            row = await cur.fetchone()
        if not row:
            return DataSourceResult(source=self.name, latency_ms=int((time.perf_counter() - start) * 1000), rows=0, data=None)
        data = Customer(**dict(row)).model_dump()
        return DataSourceResult(source=self.name, latency_ms=int((time.perf_counter() - start) * 1000), rows=1, data=data)

    async def get_transactions(self, customer_id: str, months: int = 6) -> DataSourceResult:
        start = time.perf_counter()
        async with get_async_conn() as conn:
            cur = await conn.execute(
                """
                SELECT id, customer_id, ts, amount, category, channel, merchant
                FROM transactions
                WHERE customer_id = ?
                  AND ts >= datetime('now', ?)
                ORDER BY ts DESC
                """,
                (customer_id, f"-{months * 30} days"),
            )
            rows = [dict(r) for r in await cur.fetchall()]
        txns = [Transaction(**r).model_dump() for r in rows]
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(txns),
            data=txns,
        )

    # --- Bulk fetchers: one query for many customers (kills N+1) ---

    async def get_transactions_bulk(self, customer_ids: list[str], months: int = 6) -> dict[str, list[dict[str, Any]]]:
        if not customer_ids:
            return {}
        placeholders = ",".join(["?"] * len(customer_ids))
        out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in customer_ids}
        async with get_async_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT id, customer_id, ts, amount, category, channel, merchant
                FROM transactions
                WHERE customer_id IN ({placeholders})
                  AND ts >= datetime('now', ?)
                ORDER BY ts DESC
                """,
                (*customer_ids, f"-{months * 30} days"),
            )
            for r in await cur.fetchall():
                d = dict(r)
                out.setdefault(d["customer_id"], []).append(d)
        return out

    async def get_holdings_bulk(self, customer_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not customer_ids:
            return {}
        placeholders = ",".join(["?"] * len(customer_ids))
        out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in customer_ids}
        async with get_async_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT h.customer_id, h.product_id, p.name, p.category, h.status, h.opened_at
                FROM holdings h JOIN products p ON p.id = h.product_id
                WHERE h.customer_id IN ({placeholders})
                """,
                tuple(customer_ids),
            )
            for r in await cur.fetchall():
                d = dict(r)
                out.setdefault(d["customer_id"], []).append(d)
        return out

    async def get_interactions_bulk(self, customer_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not customer_ids:
            return {}
        placeholders = ",".join(["?"] * len(customer_ids))
        out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in customer_ids}
        async with get_async_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT id, customer_id, ts, channel, summary
                FROM interactions WHERE customer_id IN ({placeholders}) ORDER BY ts DESC
                """,
                tuple(customer_ids),
            )
            for r in await cur.fetchall():
                d = dict(r)
                out.setdefault(d["customer_id"], []).append(d)
        return out

    async def get_customers_bulk(self, customer_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not customer_ids:
            return {}
        placeholders = ",".join(["?"] * len(customer_ids))
        out: dict[str, dict[str, Any]] = {}
        async with get_async_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT c.*, a.balance, a.avg_balance_6m
                FROM customers c LEFT JOIN accounts a ON a.customer_id = c.id
                WHERE c.id IN ({placeholders})
                """,
                tuple(customer_ids),
            )
            for r in await cur.fetchall():
                d = Customer(**dict(r)).model_dump()
                out[d["id"]] = d
        return out

    async def get_products(self) -> DataSourceResult:
        start = time.perf_counter()
        async with get_async_conn() as conn:
            cur = await conn.execute("SELECT * FROM products")
            rows = [dict(r) for r in await cur.fetchall()]
        products = []
        for r in rows:
            elig = json.loads(r.pop("eligibility_json", "{}") or "{}")
            r["eligibility"] = elig
            products.append(Product(**r).model_dump())
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(products),
            data=products,
        )

    async def get_holdings(self, customer_id: str) -> DataSourceResult:
        start = time.perf_counter()
        async with get_async_conn() as conn:
            cur = await conn.execute(
                """
                SELECT h.product_id, p.name, p.category, h.status, h.opened_at
                FROM holdings h
                JOIN products p ON p.id = h.product_id
                WHERE h.customer_id = ?
                """,
                (customer_id,),
            )
            rows = [dict(r) for r in await cur.fetchall()]
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(rows),
            data=rows,
        )

    async def get_interactions(self, customer_id: str | None = None) -> DataSourceResult:
        start = time.perf_counter()
        async with get_async_conn() as conn:
            if customer_id:
                cur = await conn.execute(
                    "SELECT id, customer_id, ts, channel, summary FROM interactions WHERE customer_id = ? ORDER BY ts DESC",
                    (customer_id,),
                )
            else:
                cur = await conn.execute(
                    "SELECT id, customer_id, ts, channel, summary FROM interactions ORDER BY ts DESC"
                )
            rows = [dict(r) for r in await cur.fetchall()]
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(rows),
            data=rows,
        )

    async def health(self) -> bool:
        try:
            async with get_async_conn() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("SQLite health failed: %s", e)
            return False
