"""Databricks adapter — Delta tables via the SQL connector.

Sync connector wrapped in `asyncio.to_thread`. Timeout enforced via wait_for.
On any failure the FailoverSource silently falls back to SQLite.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.domain import Customer, CustomerFilters, Product, Transaction
from app.observability import get_logger
from app.settings import get_settings

from .base import DataSource, DataSourceResult

logger = get_logger(__name__)


class DatabricksSource(DataSource):
    name = "databricks"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._catalog = self.settings.databricks_catalog
        self._schema = self.settings.databricks_schema

    # -----------------------------------------------------------------------
    # connector helpers
    # -----------------------------------------------------------------------
    def _connect(self):
        # imported lazily so the package is optional in dev
        from databricks import sql  # type: ignore[import-not-found]

        return sql.connect(
            server_hostname=self.settings.databricks_host,
            http_path=self.settings.databricks_http_path,
            access_token=self.settings.databricks_token,
        )

    def _query_sync(self, sql_text: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if params:
                cur.execute(sql_text, params)
            else:
                cur.execute(sql_text)
            cols = [c[0] for c in cur.description] if cur.description else []
            return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    async def _query(self, sql_text: str, params: tuple = ()) -> list[dict[str, Any]]:
        return await asyncio.wait_for(
            asyncio.to_thread(self._query_sync, sql_text, params),
            timeout=self.settings.databricks_timeout_seconds,
        )

    def _t(self, name: str) -> str:
        return f"{self._catalog}.{self._schema}.{name}"

    # -----------------------------------------------------------------------
    # DataSource implementation
    # -----------------------------------------------------------------------
    async def find_customers(self, filters: CustomerFilters) -> DataSourceResult:
        start = time.perf_counter()
        clauses: list[str] = []
        params: list[Any] = []
        if filters.cities:
            clauses.append("c.city IN (" + ",".join(["?"] * len(filters.cities)) + ")")
            params.extend(filters.cities)
        if filters.segments:
            clauses.append("c.segment IN (" + ",".join(["?"] * len(filters.segments)) + ")")
            params.extend(filters.segments)
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

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT c.*, a.balance, a.avg_balance_6m
            FROM {self._t('customers')} c
            LEFT JOIN {self._t('accounts')} a ON a.customer_id = c.id
            {where}
            ORDER BY a.avg_balance_6m DESC
            LIMIT {int(filters.limit)}
        """
        rows = await self._query(sql, tuple(params))
        customers = [Customer(**r).model_dump() for r in rows]
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(customers),
            data=customers,
        )

    async def get_customer(self, customer_id: str) -> DataSourceResult:
        start = time.perf_counter()
        sql = f"""
            SELECT c.*, a.balance, a.avg_balance_6m
            FROM {self._t('customers')} c
            LEFT JOIN {self._t('accounts')} a ON a.customer_id = c.id
            WHERE c.id = ?
        """
        rows = await self._query(sql, (customer_id,))
        data = Customer(**rows[0]).model_dump() if rows else None
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=1 if data else 0,
            data=data,
        )

    async def get_transactions(self, customer_id: str, months: int = 6) -> DataSourceResult:
        start = time.perf_counter()
        sql = f"""
            SELECT id, customer_id, ts, amount, category, channel, merchant
            FROM {self._t('transactions')}
            WHERE customer_id = ? AND ts >= date_sub(current_timestamp(), {int(months * 30)})
            ORDER BY ts DESC
        """
        rows = await self._query(sql, (customer_id,))
        txns = [Transaction(**r).model_dump() for r in rows]
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(txns),
            data=txns,
        )

    # --- Bulk fetchers (single IN-clause query per type) ---
    async def get_customers_bulk(self, customer_ids: list[str]) -> dict[str, Any]:
        if not customer_ids:
            return {}
        ph = ",".join(["?"] * len(customer_ids))
        sql = f"""
            SELECT c.*, a.balance, a.avg_balance_6m
            FROM {self._t('customers')} c
            LEFT JOIN {self._t('accounts')} a ON a.customer_id = c.id
            WHERE c.id IN ({ph})
        """
        rows = await self._query(sql, tuple(customer_ids))
        return {r["id"]: Customer(**r).model_dump() for r in rows}

    async def get_transactions_bulk(self, customer_ids: list[str], months: int = 6) -> dict[str, list]:
        if not customer_ids:
            return {}
        ph = ",".join(["?"] * len(customer_ids))
        sql = f"""
            SELECT id, customer_id, ts, amount, category, channel, merchant
            FROM {self._t('transactions')}
            WHERE customer_id IN ({ph}) AND ts >= date_sub(current_timestamp(), {int(months * 30)})
            ORDER BY ts DESC
        """
        rows = await self._query(sql, tuple(customer_ids))
        out: dict[str, list] = {cid: [] for cid in customer_ids}
        for r in rows:
            out.setdefault(r["customer_id"], []).append(r)
        return out

    async def get_holdings_bulk(self, customer_ids: list[str]) -> dict[str, list]:
        if not customer_ids:
            return {}
        ph = ",".join(["?"] * len(customer_ids))
        sql = f"""
            SELECT h.customer_id, h.product_id, p.name, p.category, h.status, h.opened_at
            FROM {self._t('holdings')} h JOIN {self._t('products')} p ON p.id = h.product_id
            WHERE h.customer_id IN ({ph})
        """
        rows = await self._query(sql, tuple(customer_ids))
        out: dict[str, list] = {cid: [] for cid in customer_ids}
        for r in rows:
            out.setdefault(r["customer_id"], []).append(r)
        return out

    async def get_interactions_bulk(self, customer_ids: list[str]) -> dict[str, list]:
        if not customer_ids:
            return {}
        ph = ",".join(["?"] * len(customer_ids))
        sql = f"""
            SELECT id, customer_id, ts, channel, summary
            FROM {self._t('interactions')} WHERE customer_id IN ({ph}) ORDER BY ts DESC
        """
        rows = await self._query(sql, tuple(customer_ids))
        out: dict[str, list] = {cid: [] for cid in customer_ids}
        for r in rows:
            out.setdefault(r["customer_id"], []).append(r)
        return out

    async def get_products(self) -> DataSourceResult:
        start = time.perf_counter()
        rows = await self._query(f"SELECT * FROM {self._t('products')}")
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
        sql = f"""
            SELECT h.product_id, p.name, p.category, h.status, h.opened_at
            FROM {self._t('holdings')} h
            JOIN {self._t('products')} p ON p.id = h.product_id
            WHERE h.customer_id = ?
        """
        rows = await self._query(sql, (customer_id,))
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(rows),
            data=rows,
        )

    async def get_interactions(self, customer_id: str | None = None) -> DataSourceResult:
        start = time.perf_counter()
        if customer_id:
            sql = f"SELECT id, customer_id, ts, channel, summary FROM {self._t('interactions')} WHERE customer_id = ? ORDER BY ts DESC"
            rows = await self._query(sql, (customer_id,))
        else:
            sql = f"SELECT id, customer_id, ts, channel, summary FROM {self._t('interactions')} ORDER BY ts DESC"
            rows = await self._query(sql)
        return DataSourceResult(
            source=self.name,
            latency_ms=int((time.perf_counter() - start) * 1000),
            rows=len(rows),
            data=rows,
        )

    async def health(self) -> bool:
        try:
            await self._query("SELECT 1")
            return True
        except Exception as e:  # noqa: BLE001
            logger.info("Databricks health check failed (will fail over): %s", e)
            return False
