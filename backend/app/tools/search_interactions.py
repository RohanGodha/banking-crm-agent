from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.application.tool_registry import tool
from app.infrastructure.rag import get_retriever


class SearchInteractionsIn(BaseModel):
    query: str = ""
    k: int = Field(default=5, ge=1, le=50)
    customer_id: str | None = None

    @field_validator("customer_id", mode="before")
    @classmethod
    def _only_string(cls, v: Any) -> Any:
        return v if isinstance(v, str) else None


class SearchInteractionsOut(BaseModel):
    source: str = "bm25"
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
        source=retriever.mode,
        matches=matches,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
