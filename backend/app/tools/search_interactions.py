from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from app.application.tool_registry import tool
from app.infrastructure.rag import get_retriever


class SearchInteractionsIn(BaseModel):
    query: str
    k: int = 5
    customer_id: str | None = None


class SearchInteractionsOut(BaseModel):
    source: str = "chroma+bm25"
    matches: list[dict[str, Any]]
    latency_ms: int


@tool(
    name="search_interactions",
    description=(
        "Hybrid RAG (dense + BM25 with MMR diversity re-rank) over past customer interaction "
        "notes. Returns ranked snippets with citation IDs that downstream nodes must reference."
    ),
    input_model=SearchInteractionsIn,
    output_model=SearchInteractionsOut,
)
async def search_interactions(args: SearchInteractionsIn) -> SearchInteractionsOut:
    started = time.perf_counter()
    retriever = get_retriever()
    matches = await retriever.search(args.query, k=args.k, customer_id=args.customer_id)
    return SearchInteractionsOut(
        matches=matches,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
