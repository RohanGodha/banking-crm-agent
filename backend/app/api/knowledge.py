"""Knowledge-base endpoints — NLP query over the new_features reference documents."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.auth.middleware import require_token
from app.knowledge_base import get_knowledge_base

router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(require_token)])


class AskIn(BaseModel):
    query: str

    @field_validator("query", mode="before")
    @classmethod
    def _clean(cls, v: object) -> str:
        s = (v if isinstance(v, str) else "").strip()
        if not s:
            raise ValueError("query must not be empty")
        return s[:500]


@router.post("/ask")
async def ask(body: AskIn) -> dict:
    return await get_knowledge_base().ask(body.query)


@router.get("/sources")
async def sources() -> dict:
    kb = get_knowledge_base()
    return {
        "sources": kb.sources(),
        "suggestions": [
            "What are the current RBI repo and CRR rates?",
            "How is a customer's CIBIL score derived from salary history?",
            "What documents are needed to apply for a personal loan?",
            "What is the home loan LTV limit?",
            "Explain the KYC and video KYC process.",
            "Are there foreclosure charges on a floating-rate loan?",
        ],
    }
