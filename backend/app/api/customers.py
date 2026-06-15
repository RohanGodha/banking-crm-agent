from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.middleware import require_token
from app.infrastructure.datasource import get_datasource

router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require_token)])


@router.get("/{customer_id}")
async def get_customer(customer_id: str) -> dict:
    ds = get_datasource()
    profile = await ds.get_customer(customer_id)
    if not profile.data:
        raise HTTPException(status_code=404, detail="Customer not found")
    txns = await ds.get_transactions(customer_id, 6)
    holdings = await ds.get_holdings(customer_id)
    interactions = await ds.get_interactions(customer_id)
    return {
        "customer": profile.data,
        "source": profile.source,
        "transactions": txns.data or [],
        "holdings": holdings.data or [],
        "interactions": interactions.data or [],
    }
