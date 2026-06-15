from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth.middleware import require_token
from app.db.sqlite_engine import get_async_conn

router = APIRouter(prefix="/trace", tags=["trace"], dependencies=[Depends(require_token)])


@router.get("/{session_id}")
async def get_trace(session_id: str) -> dict:
    async with get_async_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM agent_traces WHERE session_id = ? ORDER BY ts ASC",
            (session_id,),
        )
        events = [dict(r) for r in await cur.fetchall()]
        cur = await conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY ts ASC",
            (session_id,),
        )
        messages = [dict(r) for r in await cur.fetchall()]
        cur = await conn.execute(
            "SELECT * FROM outreach_drafts WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        drafts = [dict(r) for r in await cur.fetchall()]
    if not events and not messages:
        raise HTTPException(status_code=404, detail="No trace for that session")
    # Pretty-parse JSON fields
    for e in events:
        for k in ("input_json", "output_json"):
            if e.get(k):
                try:
                    e[k.replace("_json", "")] = json.loads(e[k])
                except Exception:  # noqa: BLE001
                    pass
    return {"events": events, "messages": messages, "drafts": drafts}
