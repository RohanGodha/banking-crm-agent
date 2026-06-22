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

from app.infrastructure.llm import LLMMessage, get_llm_router
from app.observability import get_logger

logger = get_logger(__name__)

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

    async def ask(self, query: str) -> dict[str, Any]:
        started = time.perf_counter()
        hits = self.search(query, k=4)
        if not hits:
            return {
                "answer": "I couldn't find that in the knowledge base. I cover RBI policies, "
                          "customer financial history and CIBIL, and RM-Client procedures (loans, KYC, EMI).",
                "sources": [],
                "excerpts": [],
                "llm_route": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        context = "\n\n".join(f"[{h['source']} > {h['title']}]\n{h['text']}" for h in hits)
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

        # Extractive fallback: when there is no real LLM, return the top excerpt verbatim
        # so the answer is still grounded in the documents.
        if route in (None, "mock") or len(answer) < 15:
            top = hits[0]
            snippet = top["text"]
            if len(snippet) > 700:
                snippet = snippet[:700].rsplit("\n", 1)[0] + " ..."
            answer = f"From {top['source']} - {top['title']}:\n\n{snippet}"
            route = route or "documents"

        return {
            "answer": answer,
            "sources": sorted({h["source"] for h in hits}),
            "excerpts": [{"source": h["source"], "title": h["title"], "score": h["score"]} for h in hits],
            "llm_route": route,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase()
