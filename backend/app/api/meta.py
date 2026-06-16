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
    # Group by category, preserving order
    grouped: dict[str, list[dict[str, str]]] = {}
    for f in FAQS:
        grouped.setdefault(f["category"], []).append({"q": f["q"], "a": f["a"]})
    return {"count": len(FAQS), "categories": grouped}


@router.get("/debug/groq-batch")
async def debug_groq_batch(n: int = 8) -> dict:
    """Diagnostic: fire N direct Groq calls and surface raw exceptions.

    Helps distinguish rate-limit (429) from auth/model errors when batch
    draft generation silently falls through to the mock provider.
    """
    import asyncio

    from app.infrastructure.llm import LLMMessage
    from app.infrastructure.llm.router import get_llm_router as _grt

    router_obj = _grt()
    groq = router_obj._grq()  # type: ignore[attr-defined]
    if groq is None:
        return {"groq_configured": False}

    async def _one(i: int) -> dict:
        try:
            r = await groq.complete(
                [LLMMessage(role="user", content=f"Say hi #{i} in 5 words.")],
                temperature=0.5,
                max_tokens=30,
            )
            return {"i": i, "ok": True, "text": r.text[:60]}
        except Exception as e:  # noqa: BLE001
            return {"i": i, "ok": False, "error": f"{type(e).__name__}: {e}"[:300]}

    results = await asyncio.gather(*[_one(i) for i in range(n)])
    return {
        "groq_configured": True,
        "ok_count": sum(1 for r in results if r["ok"]),
        "fail_count": sum(1 for r in results if not r["ok"]),
        "results": results,
    }
