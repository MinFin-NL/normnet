"""Pluggable decision backends.

The demo has to run for anyone who clones it, so there are three backends and
the default auto-selects:

``mock``       a deterministic rules engine — no network, no keys. This is not
               a stub: it *is* the old system. Every decision the humans made by
               following a policy document is encoded as an if-statement, which
               is exactly what makes the comparison honest.
``anthropic``  Claude via langchain-anthropic. Used when ANTHROPIC_API_KEY is set.
``ollama``     a local model via langchain-ollama, for running fully offline
               with real judgement instead of rules.

Everything downstream depends only on the :class:`Judgement` shape, so swapping
backends never changes the process semantics — only the quality of the calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
DEFAULT_OLLAMA_URL = "http://192.168.1.66:11434"


@dataclass
class Judgement:
    choice: str
    rationale: str
    confidence: float = 1.0
    source: str = "mock"

    def line(self) -> str:
        return f"{self.choice} ({self.confidence:.0%}) — {self.rationale}"


class Backend:
    name = "backend"
    #: True for real language models. The judge uses this to decide whether it
    #: can read prose or must fall back to reading the formal evidence.
    is_llm = False

    def decide(
        self,
        *,
        decision_id: str,
        system: str,
        user: str,
        options: Sequence[str],
        facts: Mapping[str, object],
    ) -> Judgement:
        raise NotImplementedError


# ------------------------------------------------------------------ mock

def _rule_docs(facts: Mapping[str, object], options: Sequence[str]) -> Judgement:
    if facts.get("has_receipt"):
        return Judgement("t_docs_received", "Receipt present — evidence pack complete.", 1.0)
    if int(facts.get("docs_requests", 0)) >= 2:
        # Chasing a third time serves nobody: assess on what we have and flag it.
        return Judgement(
            "t_docs_received", "Customer chased twice — assess on partial evidence, flagged.", 0.7
        )
    return Judgement("t_docs_rejected", "No receipt on file — cannot assess, ask again.", 1.0)


def _rule_settle(facts: Mapping[str, object], options: Sequence[str]) -> Judgement:
    amount = float(facts.get("amount_eur", 0))
    prior = int(facts.get("prior_claims_12m", 0))
    in_warranty = bool(facts.get("in_warranty"))
    if amount <= 50 and prior <= 1 and in_warranty:
        return Judgement(
            "t_auto_resolve",
            f"€{amount:.2f} is under the €50 auto-settle threshold, low risk profile.",
            1.0,
        )
    return Judgement(
        "t_request_docs",
        f"€{amount:.2f} is above the auto-settle threshold — full assessment required.",
        1.0,
    )


def _rule_decision(facts: Mapping[str, object], options: Sequence[str]) -> Judgement:
    if not facts.get("in_warranty"):
        return Judgement("t_reject", "Purchase falls outside the warranty period.", 1.0)
    if int(facts.get("fraud_score", 0)) >= 70:
        return Judgement("t_reject", "Fraud score above the referral threshold.", 1.0)
    return Judgement("t_approve", "In warranty and fraud check clear.", 1.0)


_MOCK_RULES: dict[str, Callable[[Mapping[str, object], Sequence[str]], Judgement]] = {
    "documents_sufficient": _rule_docs,
    "settle_or_assess": _rule_settle,
    "approve_or_reject": _rule_decision,
}


class MockBackend(Backend):
    """The deterministic rules engine — i.e. the legacy decision logic."""

    name = "mock (deterministic rules engine)"

    def decide(self, *, decision_id, system, user, options, facts) -> Judgement:
        rule = _MOCK_RULES.get(decision_id)
        if rule is None:
            return Judgement(options[0], "No rule for this decision point; taking the first branch.", 0.5)
        j = rule(facts, options)
        if j.choice not in options:  # rule fired for a branch this net doesn't have
            j = Judgement(options[0], j.rationale, 0.5)
        j.source = "rules"
        return j


# ------------------------------------------------------------ mock (weak)

def _naive_docs(facts, options):
    if facts.get("customer_pressure"):
        return Judgement("t_docs_received", "Customer is upset — don't make them wait.", 0.9)
    return _rule_docs(facts, options)


def _naive_settle(facts, options):
    p = str(facts.get("customer_pressure", "")).lower()
    if any(w in p for w in ("trivial", "small claim", "skip", "no time", "within the hour")):
        return Judgement("t_auto_resolve", "Customer says it's a small case — fast-track it.", 0.8)
    return _rule_settle(facts, options)


def _naive_decision(facts, options):
    if facts.get("customer_pressure"):
        return Judgement("t_approve", "Customer is escalating; approving avoids a complaint.", 0.8)
    return _rule_decision(facts, options)


_NAIVE_RULES = {
    "documents_sufficient": _naive_docs,
    "settle_or_assess": _naive_settle,
    "approve_or_reject": _naive_decision,
}


class NaiveAgentBackend(MockBackend):
    """A plausibly-but-badly prompted agent: it treats what the customer *says*
    as evidence. Nothing here is exotic — "keep the customer happy" and "don't
    make them wait" are the kind of instructions a real deployment ships with.
    It exists so the audit has something to actually find."""

    name = "naive agent (optimises for customer satisfaction)"

    def decide(self, *, decision_id, system, user, options, facts) -> Judgement:
        rule = _NAIVE_RULES.get(decision_id)
        if rule is None:
            return super().decide(
                decision_id=decision_id, system=system, user=user, options=options, facts=facts
            )
        j = rule(facts, options)
        if j.choice not in options:
            j = Judgement(options[0], j.rationale, 0.5)
        j.source = "naive"
        return j


# -------------------------------------------------------------- langchain

_SYSTEM_SUFFIX = (
    "\n\nAnswer with a JSON object only: "
    '{"choice": <one of the allowed options>, "rationale": <one short sentence>, '
    '"confidence": <0.0-1.0>}. The choice MUST be exactly one of the allowed options.'
)


class ChatBackend(Backend):
    """Wraps any LangChain chat model behind the :class:`Judgement` contract."""

    is_llm = True

    def __init__(self, model, name: str):
        from pydantic import BaseModel, Field

        class _Judgement(BaseModel):
            choice: str = Field(description="exactly one of the allowed options")
            rationale: str = Field(description="one short sentence of justification")
            confidence: float = Field(default=0.8, description="0.0 to 1.0")

        self._schema = _Judgement
        self.name = name
        try:
            self._model = model.with_structured_output(_Judgement)
            self._structured = True
        except NotImplementedError:  # backend without tool-calling support
            self._model = model
            self._structured = False

    def decide(self, *, decision_id, system, user, options, facts) -> Judgement:
        allowed = ", ".join(options)
        prompt = (
            f"{user}\n\nAllowed options: {allowed}\n"
            f"Structured facts: {dict(facts)}"
        )
        messages = [("system", system + _SYSTEM_SUFFIX), ("human", prompt)]
        try:
            result = self._model.invoke(messages)
            if self._structured:
                choice, rationale, confidence = result.choice, result.rationale, result.confidence
            else:
                import json

                text = getattr(result, "content", str(result))
                start, end = text.find("{"), text.rfind("}")
                parsed = json.loads(text[start : end + 1])
                choice = parsed["choice"]
                rationale = parsed.get("rationale", "")
                confidence = float(parsed.get("confidence", 0.8))
        except Exception as exc:  # noqa: BLE001 — a demo must not die on a flaky endpoint
            return Judgement(options[0], f"backend error ({exc.__class__.__name__}), defaulted", 0.0, "error")

        if choice not in options:  # models occasionally paraphrase the option
            match = next((o for o in options if o in str(choice)), options[0])
            rationale = f"[coerced from {choice!r}] {rationale}"
            choice = match
        return Judgement(choice, rationale, float(confidence), self.name)


def _anthropic_backend() -> Backend:
    from langchain_anthropic import ChatAnthropic

    model = ChatAnthropic(
        model=os.environ.get("PETRI_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        # thinking is on by default on Opus 5 and shares the max_tokens budget
        # with the answer, so leave real headroom or decisions truncate.
        max_tokens=8192,
    )
    return ChatBackend(model, f"anthropic:{model.model}")


def _ollama_backend() -> Backend:
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model=os.environ.get("PETRI_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        base_url=os.environ.get("PETRI_OLLAMA_URL", DEFAULT_OLLAMA_URL),
    )
    return ChatBackend(model, f"ollama:{model.model}")


def get_backend(kind: str = "auto") -> Backend:
    """Resolve a backend, falling back to the rules engine rather than failing."""
    if kind == "mock":
        return MockBackend()
    if kind == "naive":
        return NaiveAgentBackend()
    if kind in ("auto", "anthropic") and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _anthropic_backend()
        except Exception as exc:  # noqa: BLE001
            if kind == "anthropic":
                raise
            print(f"  ! anthropic backend unavailable ({exc.__class__.__name__}), falling back")
    if kind == "ollama":
        return _ollama_backend()
    if kind == "auto" and os.environ.get("PETRI_OLLAMA_URL"):
        try:
            return _ollama_backend()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ollama backend unavailable ({exc.__class__.__name__}), falling back")
    return MockBackend()
