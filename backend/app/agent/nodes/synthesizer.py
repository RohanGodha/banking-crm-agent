"""Synthesizer node — merges tool outputs into ranked CandidateRecord list and a text summary."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agent.state import AgentState, CandidateRecord, TraceEvent
from app.infrastructure.llm import LLMMessage, get_llm_router

_SYS = (Path(__file__).parent.parent / "prompts" / "synthesizer_system.md").read_text(encoding="utf-8")


def _by_step(state: AgentState, tool_name: str) -> dict[str, Any]:
    for tc in state.tool_calls:
        if tc.tool == tool_name and tc.ok and isinstance(tc.output, dict):
            return tc.output
    return {}


async def run_synthesizer(state: AgentState) -> AgentState:
    customers_out = _by_step(state, "query_customers").get("customers", [])
    customer_map = {c["id"]: c for c in customers_out}

    value_rows = _by_step(state, "compute_customer_value").get("customers", [])
    value_map = {r["customer_id"]: r for r in value_rows}

    prop_rows = _by_step(state, "predict_loan_propensity").get("customers", [])
    prop_map = {r["customer_id"]: r for r in prop_rows}

    recs = _by_step(state, "recommend_products").get("recommendations", [])
    rec_map: dict[str, dict[str, Any]] = {}
    for r in recs:
        if r["customer_id"] not in rec_map and r.get("eligible"):
            rec_map[r["customer_id"]] = r

    interactions = _by_step(state, "search_interactions").get("matches", [])
    citation_map: dict[str, list[str]] = {}
    for m in interactions:
        citation_map.setdefault(m["customer_id"], []).append(m["id"])

    target_product = state.plan.target_product if state.plan else None

    # Intent-aware composite weighting:
    #   Defensive / retention products (overdraft) target at-risk customers
    #   regardless of wallet size → propensity dominates.
    #   Acquisition / cross-sell products favour high-value customers → balanced.
    DEFENSIVE = {"PROD-LOAN-OD"}
    if target_product in DEFENSIVE:
        w_value, w_prop = 0.2, 0.8
    else:
        w_value, w_prop = 0.4, 0.6

    # Rank over every customer we scored. Propensity is preferred, but if that
    # step returned nothing (e.g. no product specified) we still surface the
    # customers found by value/query so a lookup never yields an empty result.
    ranked_ids = list(prop_map) or list(value_map) or list(customer_map)

    candidates: list[CandidateRecord] = []
    for cid in ranked_ids:
        prop = prop_map.get(cid, {})
        v = value_map.get(cid, {})
        val_score = float(v.get("value_score", 0.0))
        prop_score = float(prop.get("propensity_score", 0.0))
        composite = round(w_value * val_score + w_prop * prop_score, 4)
        rec = rec_map.get(cid)
        prod_id = (rec or {}).get("product_id") or target_product or "PROD-LOAN-PL"
        prod_name = (rec or {}).get("product_name") or prod_id
        cust = customer_map.get(cid) or {}

        # Top features = top contributions across value + propensity
        feats = []
        for b in prop.get("breakdown", [])[:3]:
            feats.append({**b, "kind": "propensity"})
        for b in v.get("breakdown", []):
            if len(feats) >= 5:
                break
            if abs(float(b.get("contribution") or 0)) > 0.05:
                feats.append({**b, "kind": "value"})

        rationale_bits: list[str] = []
        for f in feats[:2]:
            if f.get("rationale"):
                rationale_bits.append(f["rationale"])
        rationale = " ".join(rationale_bits) or "Strong combined value + propensity signal."

        candidates.append(
            CandidateRecord(
                customer_id=cid,
                name=cust.get("name", cid),
                city=cust.get("city", ""),
                segment=cust.get("segment", ""),
                monthly_income=cust.get("monthly_income"),
                avg_balance_6m=cust.get("avg_balance_6m") or cust.get("balance"),
                value_score=val_score,
                propensity_score=prop_score,
                composite_score=composite,
                recommended_product_id=prod_id,
                recommended_product_name=prod_name,
                top_features=feats,
                rationale=rationale,
                citations=citation_map.get(cid, []),
            )
        )

    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    from app.settings import get_settings
    top_k = get_settings().agent_top_k_candidates
    candidates = candidates[:top_k]

    # Sentiment + churn-risk enrichment over each candidate's interaction notes.
    from app.infrastructure.datasource import get_datasource
    from app.scoring.sentiment import analyze_sentiment
    ds = get_datasource()
    try:
        inter_map = await ds.get_interactions_bulk([c.customer_id for c in candidates])
    except Exception:  # noqa: BLE001
        inter_map = {}
    for c in candidates:
        s = analyze_sentiment(inter_map.get(c.customer_id, []))
        c.sentiment = s["sentiment"]
        c.escalate = s["escalate"]
        c.churn_risk = s["churn_risk"]
        c.opportunity_value = _estimate_opportunity(c.recommended_product_id, c.monthly_income, c.avg_balance_6m)
        c.next_action, c.priority = _next_action(c)

    # Re-rank so urgent/high-intent customers lead the action queue.
    candidates.sort(key=lambda c: (c.priority, -c.composite_score))
    state.candidates = candidates

    # Emit candidate events progressively for the UI
    for c in candidates:
        state.emit(TraceEvent(event="candidate", data=c.model_dump()))

    # No candidates → return a clear, honest message instead of asking the LLM
    # to summarise an empty list (which previously produced a confusing meta-reply).
    if not candidates:
        product = (state.plan.target_product if state.plan else None) or "the requested product"
        state.final_summary = (
            f"I couldn't find customers matching that request for {product}. "
            "Try loosening the criteria — e.g. a different city, a lower balance "
            "threshold, or a broader segment."
        )
        state.emit(TraceEvent(event="synth", data={"summary": state.final_summary, "candidate_count": 0}))
        return state

    # LLM summary
    router = get_llm_router()
    context_for_llm = "\n".join(
        f"- {c.name} ({c.city}, {c.segment}) — composite {c.composite_score:.2f}, "
        f"product: {c.recommended_product_name}, est. opportunity {_fmt_inr(c.opportunity_value) or 'n/a'}, "
        f"action: {c.next_action}; top signal: "
        f"{(c.top_features[0]['rationale'] if c.top_features else 'value+propensity composite')}"
        for c in candidates[:5]
    )
    resp = await router.complete(
        kind="reasoning",
        messages=[
            LLMMessage(role="system", content=_SYS),
            LLMMessage(role="user", content=f"RM asked: {state.rm_query}\n\nCandidates:\n{context_for_llm}"),
        ],
        temperature=0.4,
        max_tokens=320,
    )
    text = resp.text.strip()
    route = resp.meta.get("route_used", resp.provider)
    # Never surface generic filler: if the LLM is unavailable (mock) or returns
    # nothing, build a specific, data-grounded summary from the real candidates.
    if route == "mock" or len(text) < 20:
        text = _fallback_summary(candidates)
    state.final_summary = text
    state.emit(TraceEvent(
        event="synth",
        data={"summary": state.final_summary, "candidate_count": len(candidates)},
        llm_route=route,
        latency_ms=resp.latency_ms,
    ))
    return state


def _estimate_opportunity(product_id: str, monthly_income: float | None, avg_balance: float | None) -> float | None:
    """Rough, defensible estimate of the opportunity size (INR) to help the RM prioritise."""
    income = float(monthly_income or 0)
    balance = float(avg_balance or 0)
    if not income and not balance:
        return None
    pid = product_id or ""
    if pid == "PROD-LOAN-HL":
        return round(min(income * 60, 25_000_000), -3)
    if pid in {"PROD-LOAN-PL", "PROD-LOAN-OD"}:
        return round(min(income * 10, 4_000_000), -3)
    if pid in {"PROD-CARD-PREM", "PROD-CARD-CB"}:
        return round(min(income * 3, 1_500_000), -3)
    if pid in {"PROD-INV-SIP", "PROD-INV-FD"}:
        return round(balance * 0.3, -3)
    return round(income * 6, -3)


def _next_action(c: CandidateRecord) -> tuple[str, int]:
    """Concrete next step + priority (1 = act now ... 3 = nurture)."""
    if c.escalate or c.churn_risk:
        return "Call within 48h — retention priority", 1
    if c.propensity_score >= 0.6:
        return "Message today — high conversion intent", 1
    if c.propensity_score >= 0.4:
        return "Reach out this week", 2
    return "Add to nurture pipeline", 3


def _fmt_inr(v: float | None) -> str:
    if not v:
        return ""
    if v >= 10_000_000:
        return f"~₹{v / 10_000_000:.1f}Cr"
    if v >= 100_000:
        return f"~₹{v / 100_000:.1f}L"
    return f"~₹{v / 1_000:.0f}k"


def _fallback_summary(candidates: list[CandidateRecord]) -> str:
    top = candidates[:3]
    lines: list[str] = []
    for c in top:
        signal = (c.top_features[0].get("rationale") if c.top_features else "") or "strong value and propensity"
        opp = _fmt_inr(c.opportunity_value)
        opp_clause = f" ({opp} opportunity)" if opp else ""
        lines.append(
            f"{c.name} ({c.city}) — {c.recommended_product_name}{opp_clause}: {signal} "
            f"→ {c.next_action}"
        )
    flagged = [c.name for c in candidates if c.escalate]
    body = "Your priority calls:\n- " + "\n- ".join(lines)
    if flagged:
        body += f"\nRetention watch: {', '.join(flagged[:3])}."
    body += "\nEach has an explainable score and a ready-to-send WhatsApp draft on the right."
    return body
