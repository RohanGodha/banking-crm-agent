"""Deterministic mock LLM.

Activates when no API keys are configured. Lets the entire agent pipeline run
end-to-end offline so reviewers can exercise the system without spending money.

It returns:
  - For planner JSON requests: a sensible canned plan covering the canonical PL ask.
  - For critic JSON requests: a pass verdict.
  - For synthesizer requests: a templated final answer using whatever rendered context appears in the user message.
  - For message generation: a templated WhatsApp message using the provided customer/product context.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from .base import LLMClient, LLMMessage, LLMResponse


class MockLLM(LLMClient):
    name = "mock"
    supports_json = True

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        start = time.perf_counter()
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        system = "\n".join(m.content for m in messages if m.role == "system").lower()
        text, data = self._dispatch(system, last_user, json_mode)
        elapsed = int((time.perf_counter() - start) * 1000)
        return LLMResponse(
            text=text,
            json_data=data if json_mode else None,
            model="mock-1",
            provider=self.name,
            latency_ms=elapsed,
            tokens_in=len(last_user) // 4,
            tokens_out=len(text) // 4,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Deterministic 'hash-bag' embeddings — good enough for cosine ordering in dev."""
        dim = 256
        vectors: list[list[float]] = []
        for t in texts:
            vec = [0.0] * dim
            for word in re.findall(r"[a-zA-Z]+", t.lower()):
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
                vec[idx] += 1.0
            # L2 norm
            mag = sum(v * v for v in vec) ** 0.5 or 1.0
            vectors.append([v / mag for v in vec])
        return vectors

    async def health(self) -> bool:
        return True

    # -------------------------------------------------------------------
    # Routing inside the mock — match on **node tags**, not free-text
    # The real prompts include `[node:planner]` / `[node:critic]` etc., which
    # cannot collide with words like "CRITICAL" inside body copy.
    # -------------------------------------------------------------------
    _NODE_PATTERNS = {
        "intent":      re.compile(r"route a message from a banking"),
        "follow_up":   re.compile(r"refining their previous request|rewrite their new message"),
        "faq":         re.compile(r"knowledge base"),
        "chitchat":    re.compile(r"conversational message"),
        "guardrail":   re.compile(r"outside the scope|politely decline"),
        "planner":     re.compile(r"\[node:planner\]|decompose the rm|executable plan"),
        "critic":      re.compile(r"\[node:critic\]|the \*\*critic\*\* node|critic.{0,20}node"),
        "synthesizer": re.compile(r"\[node:synthesizer\]|the \*\*synthesizer\*\*|synthesi[sz]e"),
        "whatsapp":    re.compile(r"writing a whatsapp message"),
    }

    def _dispatch(self, system: str, user: str, json_mode: bool) -> tuple[str, dict[str, Any]]:
        u_low = user.lower()
        s = system  # already lowercased by caller
        # Most specific cues first.
        if self._NODE_PATTERNS["follow_up"].search(s):
            return self._follow_up(user)
        if self._NODE_PATTERNS["intent"].search(s):
            return self._intent(u_low)
        if self._NODE_PATTERNS["faq"].search(s):
            return self._faq()
        if self._NODE_PATTERNS["chitchat"].search(s):
            return self._chitchat(user)
        if self._NODE_PATTERNS["guardrail"].search(s):
            return self._guardrail()
        if self._NODE_PATTERNS["whatsapp"].search(s):
            return self._whatsapp(user)
        if self._NODE_PATTERNS["critic"].search(s):
            return self._critic()
        if self._NODE_PATTERNS["synthesizer"].search(s):
            return self._synthesize(user)
        if self._NODE_PATTERNS["planner"].search(s):
            return self._plan(u_low)
        if json_mode:
            data = {"ok": True, "note": "mock-llm response"}
            return json.dumps(data), data
        return ("This is a deterministic mock response. Configure GEMINI_API_KEY or "
                "GROQ_API_KEY for real LLM output."), {}

    def _intent(self, user_lower: str) -> tuple[str, dict[str, Any]]:
        # Mirror the node heuristic so offline classification is sensible.
        new_msg = user_lower.split("new message:")[-1]
        data = {"intent": "task", "reason": "mock"}
        if re.search(r"\b(you|your)\b", new_msg) and re.search(r"what|which|how|can|who|do you", new_msg):
            data["intent"] = "faq"
        elif re.match(r"\s*(hi|hey|hello|thanks|thank you|ok)", new_msg):
            data["intent"] = "chitchat"
        elif re.search(r"poem|code|weather|joke|movie|recipe", new_msg):
            data["intent"] = "out_of_scope"
        return json.dumps(data), data

    def _follow_up(self, user: str) -> tuple[str, dict[str, Any]]:
        prev = re.search(r"Previous:\s*'([^']*)'", user)
        new = re.search(r"New:\s*'([^']*)'", user)
        base = prev.group(1) if prev else ""
        ref = new.group(1) if new else ""
        rewritten = f"{base} ({ref})".strip() if base else ref
        data = {"rewritten": rewritten}
        return json.dumps(data), data

    def _faq(self) -> tuple[str, dict[str, Any]]:
        text = (
            "I can find high-value customers, score their likelihood to convert, recommend a "
            "suitable product, and draft compliance-checked WhatsApp outreach for your review. "
            "Try: \"Find affluent customers in Mumbai for a personal loan and draft messages.\""
        )
        return text, {"summary": text}

    def _chitchat(self, user: str) -> tuple[str, dict[str, Any]]:
        name = "Rohan"
        m = re.search(r"rm name:\s*([A-Za-z]+)", user, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
        said = ""
        sm = re.search(r"rm just said:\s*(.+)", user, re.IGNORECASE | re.DOTALL)
        if sm:
            said = sm.group(1).lower()
        if re.search(r"\b(bye|goodbye|see (you|ya)|cya|take care|good ?night|later)\b", said):
            text = f"See you, {name}. I'll be here when you need the next set of customers to target."
        elif re.search(r"\b(thanks?|thank you|thx|cheers)\b", said):
            text = f"Anytime, {name}. Tell me the segment or product whenever you're ready."
        elif re.search(r"\b(how are you|how'?s it going|what'?s up|sup)\b", said):
            text = f"Ready to go, {name}. Point me at a segment or product and I'll find and score the customers."
        else:
            text = (
                f"Hi {name}! I'm RM Copilot. Tell me which customers to target and I'll find them, "
                "score conversion likelihood, recommend a product, and draft WhatsApp outreach."
            )
        return text, {"summary": text}

    def _guardrail(self) -> tuple[str, dict[str, Any]]:
        text = (
            "That's outside what I can help with. I'm your banking CRM copilot — I find customers, "
            "score conversion likelihood, recommend products, and draft outreach."
        )
        return text, {"summary": text}

    # -------------------------------------------------------------------
    def _plan(self, user_lower: str) -> tuple[str, dict[str, Any]]:
        # Heuristic plan steps based on the user's ask
        product_hint = "PROD-LOAN-PL"
        if "credit card" in user_lower or "card" in user_lower:
            product_hint = "PROD-CARD-PREM"
        elif "sip" in user_lower or "mutual fund" in user_lower or "invest" in user_lower:
            product_hint = "PROD-INV-SIP"
        elif "overdraft" in user_lower or "slowdown" in user_lower or "retention" in user_lower:
            product_hint = "PROD-LOAN-OD"

        city_filter: list[str] = []
        for city in ["mumbai", "bangalore", "delhi", "pune", "hyderabad", "chennai", "kolkata"]:
            if city in user_lower:
                city_filter.append(city.capitalize())

        language = "English"
        for lang in ["hindi", "marathi", "tamil", "telugu", "kannada", "gujarati", "bengali", "punjabi"]:
            if lang in user_lower:
                language = lang.capitalize()
                break

        # Build a sensible default plan that matches the real tool signatures.
        # Looser filters when the ask sounds retention-flavoured.
        is_retention = product_hint == "PROD-LOAN-OD" or "slowdown" in user_lower
        plan = {
            "intent": "find_high_value_customers_and_outreach",
            "target_product": product_hint,
            "city_filter": city_filter,
            "tone": (
                "warm" if "warm" in user_lower
                else ("formal" if "formal" in user_lower else "professional")
            ),
            "language": language,
            "steps": [
                {
                    "step": 1, "tool": "query_customers",
                    "args": {
                        "cities": city_filter or None,
                        # Retention targets are not necessarily high-balance, so we
                        # do not gate them by balance — we let propensity surface them.
                        "min_balance": (None if is_retention else 200000),
                        "limit": (200 if is_retention else 80),
                        "exclude_products": [product_hint],
                    },
                    "expected": "Shortlist of candidate customers.",
                },
                {
                    "step": 2, "tool": "compute_customer_value",
                    "args": {"customer_ids": "$step1.ids"},
                    "expected": "Value score per customer with feature contributions.",
                },
                {
                    "step": 3, "tool": "predict_loan_propensity",
                    # Score propensity for the *whole* queried set, not just the
                    # value-top slice, so high-propensity / moderate-value customers
                    # (e.g. retention targets) are not filtered out prematurely.
                    "args": {"customer_ids": "$step1.ids", "product_id": product_hint},
                    "expected": "Propensity score and feature drivers per candidate.",
                },
                {
                    "step": 4, "tool": "recommend_products",
                    "args": {
                        "customer_ids": "$step3.top_k",
                        "candidate_product_ids": [product_hint],
                        "top_k": 1,
                    },
                    "expected": "Eligibility-checked product recommendation per customer.",
                },
                {
                    "step": 5, "tool": "search_interactions",
                    "args": {"query": user_lower[:80], "k": 5},
                    "expected": "RAG snippets to ground messages.",
                },
            ],
        }
        return json.dumps(plan), plan

    def _critic(self) -> tuple[str, dict[str, Any]]:
        data = {"verdict": "pass", "replan": False, "notes": "Subtask satisfied; proceed."}
        return json.dumps(data), data

    def _synthesize(self, user: str) -> tuple[str, dict[str, Any]]:
        # The agent feeds rendered context into `user`; we echo a clean answer.
        text = (
            "Here are the highest-priority customers for this campaign, ranked by combined "
            "value and propensity. Each one carries an explainable score breakdown and a "
            "compliance-checked WhatsApp draft. Review the right pane to approve or refine."
        )
        return text, {"summary": text}

    def _whatsapp(self, user: str) -> tuple[str, dict[str, Any]]:
        """Build a data-grounded draft from the structured payload (name, product, signals)."""
        name = "there"
        product = "this offering"
        rm = "Rohan"
        cust_match = re.search(r"Customer:\s*\n\s*name:\s*([^\n]+)", user, re.IGNORECASE)
        if cust_match:
            name = cust_match.group(1).strip().split()[0]
        prod_match = re.search(r"Product:\s*\n\s*name:\s*([^\n]+)", user, re.IGNORECASE)
        if prod_match:
            product = prod_match.group(1).strip()
        rm_match = re.search(r"RM:\s*([A-Za-z]+)", user)
        if rm_match:
            rm = rm_match.group(1).strip()

        signals = user.lower()
        if "no active loan" in signals or "no_existing_loan" in signals:
            observation = "I noticed you don't currently hold a loan with us"
        elif "balance" in signals:
            observation = "given the healthy balances you maintain with us"
        elif "salary" in signals or "income" in signals:
            observation = "based on your salary relationship with us"
        elif "large" in signals and "debit" in signals:
            observation = "following some recent large transactions on your account"
        else:
            observation = "based on your recent activity with us"

        warm = "warm" in signals
        opener = f"Hi {name}," if warm else f"Hello {name},"
        text = (
            f"{opener} {observation}, our {product} could be a strong fit for you. "
            f"I'd be glad to walk you through the specifics — would a quick call this week work? — {rm}"
        )
        return text, {"message": text}
