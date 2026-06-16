from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from app.application.tool_registry import tool
from app.domain import ScoreBreakdown
from app.infrastructure.datasource import get_datasource
from app.infrastructure.llm import LLMMessage, get_llm_router
from app.scoring.compliance import compliance_check


class GenerateWhatsAppIn(BaseModel):
    customer_id: str
    product_id: str
    tone: str = Field(default="professional", description="warm | formal | professional | concise")
    top_features: list[ScoreBreakdown] = Field(default_factory=list)
    rm_name: str = "Rohan"


class GenerateWhatsAppOut(BaseModel):
    customer_id: str
    product_id: str
    message: str
    compliance: dict[str, Any]
    llm_route: str
    latency_ms: int


from app.agent.prompts import WHATSAPP_PROMPT as _SYSTEM_PROMPT


def _user_prompt(customer: dict[str, Any], product: dict[str, Any], top_features: list[ScoreBreakdown], tone: str, rm_name: str) -> str:
    feat_lines = "\n".join(
        f"- {f.feature}: contribution={f.contribution:+.2f}  ({f.rationale})"
        for f in top_features[:3]
    )
    return (
        f"Customer:\n"
        f"  name: {customer.get('name')}\n"
        f"  city: {customer.get('city')}\n"
        f"  segment: {customer.get('segment')}\n"
        f"  age: {customer.get('age')}\n"
        f"Product:\n"
        f"  name: {product.get('name')}\n"
        f"  category: {product.get('category')}\n"
        f"  description: {product.get('description')}\n"
        f"Top signals:\n{feat_lines or '  (none)'}\n"
        f"Tone: {tone}\n"
        f"RM: {rm_name}\n"
        f"\nWrite the WhatsApp message now."
    )


@tool(
    name="generate_whatsapp_message",
    description=(
        "Generate a compliance-validated WhatsApp draft for one customer + one product, "
        "grounded in the supplied top feature contributions. Numeric grounding validator strips "
        "any ungrounded number from the final draft."
    ),
    input_model=GenerateWhatsAppIn,
    output_model=GenerateWhatsAppOut,
)
async def generate_whatsapp_message(args: GenerateWhatsAppIn) -> GenerateWhatsAppOut:
    started = time.perf_counter()
    ds = get_datasource()
    profile_res = await ds.get_customer(args.customer_id)
    prods_res = await ds.get_products()
    products: list[dict[str, Any]] = prods_res.data or []
    product = next((p for p in products if p["id"] == args.product_id), None)
    if not profile_res.data or not product:
        return GenerateWhatsAppOut(
            customer_id=args.customer_id,
            product_id=args.product_id,
            message="",
            compliance={"ok": False, "error": "customer_or_product_not_found"},
            llm_route="-",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    customer = profile_res.data
    router = get_llm_router()
    resp = await router.complete(
        kind="generation",
        messages=[
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=_user_prompt(customer, product, args.top_features, args.tone, args.rm_name)),
        ],
        temperature=0.6,
        max_tokens=220,
    )
    draft = resp.text.strip().strip('"').strip("'")

    # Compliance grounding
    source_context = {
        "customer": customer,
        "product": product,
        "features": [f.model_dump() for f in args.top_features],
    }
    report = compliance_check(draft, source_context)
    final_msg = report["redacted_draft"] if not report["ok"] else draft

    return GenerateWhatsAppOut(
        customer_id=args.customer_id,
        product_id=args.product_id,
        message=final_msg,
        compliance=report,
        llm_route=resp.meta.get("route_used", resp.provider),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
