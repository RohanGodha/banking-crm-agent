"""FailoverSource — tries primary (Databricks), falls back to secondary (SQLite).

Every result still carries `source` so the trace panel shows which path served the call.
A failed primary call also marks a short-lived circuit-breaker so we don't retry every tool.
"""
from __future__ import annotations

import time
from typing import Any

from app.observability import get_logger

from .base import DataSource, DataSourceResult

logger = get_logger(__name__)


class FailoverSource(DataSource):
    name = "failover"

    def __init__(self, primary: DataSource, secondary: DataSource, breaker_seconds: int = 60) -> None:
        self.primary = primary
        self.secondary = secondary
        self.breaker_seconds = breaker_seconds
        self._breaker_open_until: float = 0.0

    def _breaker_open(self) -> bool:
        return time.time() < self._breaker_open_until

    def _trip(self) -> None:
        self._breaker_open_until = time.time() + self.breaker_seconds
        logger.warning("Primary DataSource breaker tripped for %ds.", self.breaker_seconds)

    async def _call(self, method: str, *args, **kwargs) -> DataSourceResult:
        if not self._breaker_open():
            try:
                fn = getattr(self.primary, method)
                return await fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                logger.info("Primary %s failed (%s) — failing over.", method, e.__class__.__name__)
                self._trip()
        fn = getattr(self.secondary, method)
        result: DataSourceResult = await fn(*args, **kwargs)
        # mark fallback source explicitly
        return result.model_copy(update={"source": f"{self.secondary.name}(failover)"})

    async def find_customers(self, filters: Any) -> DataSourceResult:
        return await self._call("find_customers", filters)

    async def get_customer(self, customer_id: str) -> DataSourceResult:
        return await self._call("get_customer", customer_id)

    async def get_transactions(self, customer_id: str, months: int = 6) -> DataSourceResult:
        return await self._call("get_transactions", customer_id, months)

    async def get_products(self) -> DataSourceResult:
        return await self._call("get_products")

    async def get_holdings(self, customer_id: str) -> DataSourceResult:
        return await self._call("get_holdings", customer_id)

    async def get_interactions(self, customer_id: str | None = None) -> DataSourceResult:
        return await self._call("get_interactions", customer_id)

    # --- Bulk fetchers delegate through the same breaker logic ---
    async def _call_bulk(self, method: str, *args, **kwargs):
        if not self._breaker_open() and hasattr(self.primary, method):
            try:
                return await getattr(self.primary, method)(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                logger.info("Primary %s failed (%s) — failing over.", method, e.__class__.__name__)
                self._trip()
        return await getattr(self.secondary, method)(*args, **kwargs)

    async def get_transactions_bulk(self, customer_ids, months: int = 6):
        return await self._call_bulk("get_transactions_bulk", customer_ids, months)

    async def get_holdings_bulk(self, customer_ids):
        return await self._call_bulk("get_holdings_bulk", customer_ids)

    async def get_interactions_bulk(self, customer_ids):
        return await self._call_bulk("get_interactions_bulk", customer_ids)

    async def get_customers_bulk(self, customer_ids):
        return await self._call_bulk("get_customers_bulk", customer_ids)

    async def health(self) -> bool:
        try:
            return await self.primary.health() or await self.secondary.health()
        except Exception:  # noqa: BLE001
            return await self.secondary.health()
