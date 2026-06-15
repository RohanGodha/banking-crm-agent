"""SSE-streamed chat endpoint. Drives the entire agent run."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent import AgentState, run_agent
from app.auth.middleware import require_token
from app.db.sqlite_engine import get_async_conn

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_token)])


class ChatStreamIn(BaseModel):
    session_id: str | None = None
    rm_query: str
    rm_name: str = "Rohan"


async def _ensure_session(session_id: str | None, query: str) -> str:
    if session_id:
        return session_id
    sid = str(uuid.uuid4())
    async with get_async_conn() as conn:
        await conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)",
            (sid, _title_from_query(query)),
        )
        await conn.commit()
    return sid


def _title_from_query(q: str) -> str:
    q = q.strip().rstrip("?.! ")
    return (q[:60] + "...") if len(q) > 63 else q


async def _persist_user_msg(session_id: str, content: str) -> None:
    async with get_async_conn() as conn:
        await conn.execute(
            "INSERT INTO messages (id, session_id, role, content) VALUES (lower(hex(randomblob(8))), ?, 'user', ?)",
            (session_id, content),
        )
        await conn.execute("UPDATE sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
        await conn.commit()


@router.post("/stream")
async def chat_stream(req: ChatStreamIn, request: Request) -> EventSourceResponse:
    session_id = await _ensure_session(req.session_id, req.rm_query)
    await _persist_user_msg(session_id, req.rm_query)

    state = AgentState(session_id=session_id, rm_query=req.rm_query, rm_name=req.rm_name)

    async def event_gen() -> AsyncIterator[dict]:
        yield {"event": "info", "data": json.dumps({"session_id": session_id})}
        try:
            async for ev in run_agent(state):
                if await request.is_disconnected():
                    break
                yield {"event": ev.event, "data": ev.model_dump_json()}
                # tiny throttle so the UI can paint between events
                await asyncio.sleep(0.005)
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"error": f"{type(e).__name__}: {e}"})}

    return EventSourceResponse(event_gen(), ping=15)


# ---- non-streaming convenience for tests ----

@router.post("/run")
async def chat_run(req: ChatStreamIn) -> dict:
    session_id = await _ensure_session(req.session_id, req.rm_query)
    await _persist_user_msg(session_id, req.rm_query)
    state = AgentState(session_id=session_id, rm_query=req.rm_query, rm_name=req.rm_name)
    events = []
    async for ev in run_agent(state):
        events.append(ev.model_dump())
    return {
        "session_id": session_id,
        "summary": state.final_summary,
        "candidates": [c.model_dump() for c in state.candidates],
        "drafts": [d.model_dump() for d in state.drafts],
        "events": events,
    }
