"""Meta endpoints — capabilities, products, example prompts, FAQs, domain + live status.

Powers the frontend "Guide" panel so the RM can see exactly what the agent does,
which domain it operates in, and browse the full FAQ set.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.knowledge import CAPABILITIES, DOMAIN, EXAMPLE_PROMPTS, FAQS, PRODUCTS
from app.auth.middleware import require_token
from app.infrastructure.datasource import get_datasource
from app.infrastructure.llm import get_llm_router

router = APIRouter(prefix="/meta", tags=["meta"], dependencies=[Depends(require_token)])


@router.get("/capabilities")
async def capabilities() -> dict:
    ds = get_datasource()
    llm = get_llm_router()
    providers = llm.status()
    active = [k for k, v in providers.items() if v and k != "mock"]
    return {
        "domain": DOMAIN,
        "capabilities": CAPABILITIES,
        "products": PRODUCTS,
        "example_prompts": EXAMPLE_PROMPTS,
        "faq_count": len(FAQS),
        "status": {
            "datasource": getattr(ds, "name", "unknown"),
            "llm": (" + ".join(active)) if active else "mock (offline)",
            "rag": "hybrid (BM25 + dense)",
        },
    }


@router.get("/faqs")
async def faqs() -> dict:
    grouped: dict[str, list[dict[str, str]]] = {}
    for f in FAQS:
        grouped.setdefault(f["category"], []).append({"q": f["q"], "a": f["a"]})
    return {"count": len(FAQS), "categories": grouped}
