from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.tool_registry import get_registry, invoke_tool
from app.auth.middleware import require_token

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(require_token)])


@router.get("")
async def list_tools() -> dict:
    registry = get_registry()
    return {
        "tools": [spec.json_schema() for spec in registry.values()],
        "count": len(registry),
    }


@router.post("/{name}")
async def call_tool(name: str, payload: dict) -> dict:
    return await invoke_tool(name, payload or {})
