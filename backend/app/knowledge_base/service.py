"""Real-time knowledge base over the new_features markdown documents.

Answers RM-Client questions by retrieving the most relevant document sections
(BM25 over markdown chunks) and grounding an LLM answer in them. Falls back to an
extractive answer from the documents when no LLM is available - so answers always
come from the documents, not the model's memory or only the database.
"""
from __future__ import annotations

import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.domain import CustomerFilters
from app.infrastructure.datasource import get_datasource
from app.infrastructure.llm import LLMMessage, get_llm_router
from app.observability import get_logger

logger = get_logger(__name__)

_LOAN_CATEGORIES = {"loan", "overdraft"}
_STOPWORDS = {
    "tell", "show", "give", "list", "what", "which", "past", "loan", "loans", "taken",
    "by", "me", "the", "a", "an", "of", "for", "is", "are", "do", "does", "has", "have",
    "about", "history", "data", "customer", "client", "his", "her", "their", "and",
}

_KB_DIR = Path(__file__).resolve().parents[2] / "new_features"
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_HEADING_RE = re.compile(r"^#{1,4}\s+(.*)$")

_FILES = {
    "rbi_policies.md": "RBI Policies",
    "customer_financial_history.md": "Customer Financial History",
    "rm_client_faqs.md": "RM-Client FAQs",
}

_SYSTEM = (
    "You are RM Copilot's knowledge assistant for a banking Relationship Manager. "
    "Answer ONLY from the reference excerpts provided. Be concise, factual and practical. "
    "Use Indian banking context and Rupees. If the answer is not in the excerpts, say you "
    "don't have that in the knowledge base and suggest what is covered. Never invent figures."
)


def _tokenize(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(s)]


class KnowledgeBase:
    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
        self._ready = False
        self._name_index: dict[str, dict[str, Any]] | None = None

    def _ensure(self) -> None:
        if self._ready:
            return
        chunks: list[dict[str, Any]] = []
        for fname, label in _FILES.items():
            path = _KB_DIR / fname
            if not path.exists():
                logger.warning("Knowledge file missing: %s", path)
                continue
            chunks.extend(self._split(path.read_text(encoding="utf-8"), label))
        self._chunks = chunks
        if chunks:
            self._bm25 = BM25Okapi([_tokenize(c["title"] + " " + c["text"]) for c in chunks])
        self._ready = True
        logger.info("KnowledgeBase ready: %d chunks from %d docs.", len(chunks), len(_FILES))

    @staticmethod
    def _split(text: str, source: str) -> list[dict[str, Any]]:
        """Split markdown into chunks at ## / ### headings, keeping each section together."""
        lines = text.splitlines()
        chunks: list[dict[str, Any]] = []
        title = source
        buf: list[str] = []

        def flush() -> None:
            body = "\n".join(buf).strip()
            if len(body) >= 20:
                chunks.append({"source": source, "title": title, "text": body})

        for line in lines:
            m = _HEADING_RE.match(line)
            if m and line.startswith("##"):
                flush()
                buf = []
                title = m.group(1).strip()
            else:
                buf.append(line)
        flush()
        return chunks

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        self._ensure()
        if not self._chunks or not self._bm25:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(self._chunks)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in ranked[:k]:
            if scores[i] <= 0:
                continue
            c = self._chunks[i]
            out.append({"source": c["source"], "title": c["title"], "text": c["text"], "score": round(float(scores[i]), 3)})
        return out

    def sources(self) -> list[dict[str, Any]]:
        self._ensure()
        grouped: dict[str, list[str]] = {}
        for c in self._chunks:
            grouped.setdefault(c["source"], [])
            if c["title"] not in grouped[c["source"]] and c["title"] != c["source"]:
                grouped[c["source"]].append(c["title"])
        return [{"source": s, "sections": sections} for s, sections in grouped.items()]

    async def _name_map(self) -> dict[str, dict[str, Any]]:
        """First-name (lowercase) -> customer record. Hero personas win ties."""
        if self._name_index is not None:
            return self._name_index
        index: dict[str, dict[str, Any]] = {}
        try:
            res = await get_datasource().find_customers(CustomerFilters(limit=2000))
            for c in res.data or []:
                name = (c.get("name") or "").strip()
                if not name:
                    continue
                first = name.split()[0].lower()
                existing = index.get(first)
                if existing is None or (
                    str(c.get("id", "")).startswith("CUST-HERO") and not str(existing.get("id", "")).startswith("CUST-HERO")
                ):
                    index[first] = c
        except Exception as e:  # noqa: BLE001
            logger.warning("KB name index build failed: %s", e)
        self._name_index = index
        return index

    async def _resolve_customer(self, query: str) -> dict[str, Any] | None:
        names = await self._name_map()
        if not names:
            return None
        for tok in _tokenize(query):
            if tok in _STOPWORDS or len(tok) < 3:
                continue
            if tok in names:
                return names[tok]
        return None

    async def _customer_context(self, customer: dict[str, Any]) -> tuple[str, str]:
        """Build (LLM grounding, extractive fallback) from the customer's real records."""
        ds = get_datasource()
        cid = customer["id"]
        try:
            holdings = (await ds.get_holdings(cid)).data or []
        except Exception:  # noqa: BLE001
            holdings = []
        try:
            interactions = (await ds.get_interactions(cid)).data or []
        except Exception:  # noqa: BLE001
            interactions = []

        loans = [h for h in holdings if (h.get("category") or "").lower() in _LOAN_CATEGORIES]
        others = [h for h in holdings if (h.get("category") or "").lower() not in _LOAN_CATEGORIES]
        name = customer.get("name", cid)

        def _hold_line(h: dict[str, Any]) -> str:
            opened = (h.get("opened_at") or "")[:10]
            return f"{h.get('name')} ({h.get('category')}), status {h.get('status', 'active')}" + (f", opened {opened}" if opened else "")

        loans_txt = "; ".join(_hold_line(h) for h in loans) if loans else "none on record"
        others_txt = "; ".join(_hold_line(h) for h in others) if others else "none"
        notes = " | ".join((i.get("summary") or "")[:160] for i in interactions[:2])

        ctx = (
            f"[Customer Record]\n"
            f"Name: {name} | City: {customer.get('city')} | Segment: {customer.get('segment')}\n"
            f"Monthly income: Rs {int(customer.get('monthly_income') or 0):,} | "
            f"Avg 6m balance: Rs {int(customer.get('avg_balance_6m') or customer.get('balance') or 0):,}\n"
            f"Active loans: {loans_txt}\n"
            f"Other products held: {others_txt}\n"
            f"Recent interaction notes: {notes or 'none'}"
        )

        if loans:
            extract = f"{name} currently holds these loan facilities: {loans_txt}."
        else:
            extract = (
                f"{name} has no active or past loans on record. "
                f"Products held: {others_txt}."
            )
        return ctx, extract

    async def ask(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        customer = await self._resolve_customer(query)
        hits = self.search(query, k=3 if customer else 4)

        context_parts: list[str] = []
        extractive_primary: str | None = None
        sources: list[str] = []

        if customer:
            cust_ctx, extractive_primary = await self._customer_context(customer)
            context_parts.append(cust_ctx)
            sources.append("Customer Record")

        if hits:
            context_parts.append(
                "\n\n".join(f"[{h['source']} > {h['title']}]\n{h['text']}" for h in hits)
            )
            sources.extend(sorted({h["source"] for h in hits}))

        if not context_parts:
            return {
                "answer": "I couldn't find that in the knowledge base. I cover RBI policies, customer "
                          "financial history and CIBIL, RM-Client procedures, and specific customer records.",
                "sources": [],
                "excerpts": [],
                "llm_route": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        context = "\n\n".join(context_parts)
        router = get_llm_router()
        answer = ""
        route = None
        try:
            resp = await router.complete(
                kind="reasoning",
                messages=[
                    LLMMessage(role="system", content=_SYSTEM),
                    LLMMessage(role="user", content=f"Question: {query}\n\nReference excerpts:\n{context}"),
                ],
                temperature=0.2,
                max_tokens=320,
            )
            answer = resp.text.strip()
            route = resp.meta.get("route_used", resp.provider)
        except Exception as e:  # noqa: BLE001
            logger.warning("KB LLM answer failed (%s) - using extractive fallback.", e.__class__.__name__)

        # Extractive fallback so the answer is always grounded in real data/docs.
        if route in (None, "mock") or len(answer) < 15:
            if extractive_primary:
                answer = extractive_primary
            else:
                top = hits[0]
                snippet = top["text"]
                if len(snippet) > 700:
                    snippet = snippet[:700].rsplit("\n", 1)[0] + " ..."
                answer = f"From {top['source']} - {top['title']}:\n\n{snippet}"
            route = route or "documents"

        excerpts = [{"source": h["source"], "title": h["title"], "score": h["score"]} for h in hits]
        if customer:
            excerpts.insert(0, {"source": "Customer Record", "title": customer.get("name", ""), "score": 1.0})

        return {
            "answer": answer,
            "sources": list(dict.fromkeys(sources)),
            "excerpts": excerpts,
            "llm_route": route,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase()
