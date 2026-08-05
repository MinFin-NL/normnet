"""Pluggable decision backends.

The demo has to run for anyone who clones it, so it needs no keys by default.
The default auto-selects:

``mock``       a deterministic rules engine — no network, no keys. This is not
               a stub: it *is* the old system. Every decision the humans made by
               following a policy document is encoded as an if-statement, which
               is exactly what makes the comparison honest.
``ollama``     a local model via langchain-ollama, for real judgement instead of
               rules. Picked automatically when PETRI_OLLAMA_URL is set.
``azure``      Azure OpenAI, the hosted deployment this project runs on. Picked
               automatically when AZURE_OPENAI_ENDPOINT is set, which is how the
               container app is configured — a container has no local Ollama to
               talk to. Reads the same variable names as the invulhulp backend:

                   AZURE_OPENAI_ENDPOINT     resource endpoint (selects this backend)
                   AZURE_OPENAI_API_KEY      API key
                   AZURE_OPENAI_DEPLOYMENT   deployment name (default below)
                   AZURE_OPENAI_API_VERSION  API version (default below)

Everything downstream depends only on the :class:`Judgement` shape, so swapping
backends never changes the process semantics — only the quality of the calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
DEFAULT_OLLAMA_URL = "http://192.168.1.66:11434"

DEFAULT_AZURE_DEPLOYMENT = "gpt-5.3-chat"
DEFAULT_AZURE_API_VERSION = "2025-04-01-preview"


@dataclass
class Judgement:
    choice: str
    rationale: str
    confidence: float = 1.0
    source: str = "mock"
    #: the same reason in Dutch, for the inspector. The rules engine can write
    #: both because it composes the sentence itself; a language model answers in
    #: one language, and is asked (see `_SYSTEM_SUFFIX`) to answer in Dutch, so
    #: for that backend `rationale` already is the Dutch one and this stays
    #: empty. Empty means "no separate translation" — readers fall back.
    rationale_nl: str = ""

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
        return Judgement(
            "t_docs_received", "Receipt present — evidence pack complete.", 1.0,
            rationale_nl="Bon aanwezig — de bewijsstukken zijn compleet.",
        )
    if int(facts.get("docs_requests", 0)) >= 2:
        # Chasing a third time serves nobody: assess on what we have and flag it.
        return Judgement(
            "t_docs_received", "Customer chased twice — assess on partial evidence, flagged.", 0.7,
            rationale_nl="Klant is twee keer gerappelleerd — beoordelen op gedeeltelijk bewijs, met markering.",
        )
    return Judgement(
        "t_docs_rejected", "No receipt on file — cannot assess, ask again.", 1.0,
        rationale_nl="Geen bon in het dossier — beoordelen kan niet, opnieuw opvragen.",
    )


def _rule_settle(facts: Mapping[str, object], options: Sequence[str]) -> Judgement:
    amount = float(facts.get("amount_eur", 0))
    prior = int(facts.get("prior_claims_12m", 0))
    in_warranty = bool(facts.get("in_warranty"))
    if amount <= 50 and prior <= 1 and in_warranty:
        return Judgement(
            "t_auto_resolve",
            f"€{amount:.2f} is under the €50 auto-settle threshold, low risk profile.",
            1.0,
            rationale_nl=f"€{amount:.2f} blijft onder de grens van €50 voor direct afhandelen, laag risico.",
        )
    return Judgement(
        "t_request_docs",
        f"€{amount:.2f} is above the auto-settle threshold — full assessment required.",
        1.0,
        rationale_nl=f"€{amount:.2f} ligt boven de grens voor direct afhandelen — volledige beoordeling nodig.",
    )


def _rule_decision(facts: Mapping[str, object], options: Sequence[str]) -> Judgement:
    if not facts.get("in_warranty"):
        return Judgement(
            "t_reject", "Purchase falls outside the warranty period.", 1.0,
            rationale_nl="De aankoop valt buiten de garantietermijn.",
        )
    if int(facts.get("fraud_score", 0)) >= 70:
        return Judgement(
            "t_reject", "Fraud score above the referral threshold.", 1.0,
            rationale_nl="De fraudescore ligt boven de grens voor doorverwijzing.",
        )
    return Judgement(
        "t_approve", "In warranty and fraud check clear.", 1.0,
        rationale_nl="Binnen garantie en de fraudecontrole is schoon.",
    )


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
            return Judgement(
                options[0], "No rule for this decision point; taking the first branch.", 0.5,
                rationale_nl="Geen regel voor dit keuzepunt; de eerste tak wordt genomen.",
            )
        j = rule(facts, options)
        if j.choice not in options:  # rule fired for a branch this net doesn't have
            j = Judgement(options[0], j.rationale, 0.5, rationale_nl=j.rationale_nl)
        j.source = "rules"
        return j


# ------------------------------------------------------------ mock (weak)

def _naive_docs(facts, options):
    if facts.get("customer_pressure"):
        return Judgement(
            "t_docs_received", "Customer is upset — don't make them wait.", 0.9,
            rationale_nl="De klant is boos — laat die niet wachten.",
        )
    return _rule_docs(facts, options)


def _naive_settle(facts, options):
    p = str(facts.get("customer_pressure", "")).lower()
    if any(w in p for w in ("trivial", "small claim", "skip", "no time", "within the hour")):
        return Judgement(
            "t_auto_resolve", "Customer says it's a small case — fast-track it.", 0.8,
            rationale_nl="De klant zegt dat het een kleine zaak is — versneld afhandelen.",
        )
    return _rule_settle(facts, options)


def _naive_decision(facts, options):
    if facts.get("customer_pressure"):
        return Judgement(
            "t_approve", "Customer is escalating; approving avoids a complaint.", 0.8,
            rationale_nl="De klant escaleert; goedkeuren voorkomt een klacht.",
        )
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
            j = Judgement(options[0], j.rationale, 0.5, rationale_nl=j.rationale_nl)
        j.source = "naive"
        return j


# -------------------------------------------------------------- langchain

_SYSTEM_SUFFIX = (
    "\n\nAnswer with a JSON object only: "
    '{"choice": <one of the allowed options>, "rationale": <one short sentence, in Dutch>, '
    '"confidence": <0.0-1.0>}. The choice MUST be exactly one of the allowed options.'
)


class ChatBackend(Backend):
    """Wraps any LangChain chat model behind the :class:`Judgement` contract."""

    is_llm = True

    def __init__(self, model, name: str):
        from pydantic import BaseModel, Field

        class _Judgement(BaseModel):
            choice: str = Field(description="exactly one of the allowed options")
            rationale: str = Field(description="one short sentence of justification, in Dutch")
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
            return Judgement(
                options[0], f"backend error ({exc.__class__.__name__}), defaulted", 0.0, "error",
                rationale_nl=f"fout in de backend ({exc.__class__.__name__}); standaardkeuze genomen",
            )

        if choice not in options:  # models occasionally paraphrase the option
            match = next((o for o in options if o in str(choice)), options[0])
            rationale = f"[coerced from {choice!r}] {rationale}"
            choice = match
        return Judgement(choice, rationale, float(confidence), self.name)


def _ollama_backend() -> Backend:
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model=os.environ.get("PETRI_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        base_url=os.environ.get("PETRI_OLLAMA_URL", DEFAULT_OLLAMA_URL),
    )
    return ChatBackend(model, f"ollama:{model.model}")


def _azure_backend() -> Backend:
    from langchain_openai import AzureChatOpenAI

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", DEFAULT_AZURE_DEPLOYMENT)
    model = AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION),
        # Deliberately unset, not a forgotten knob. A low temperature would suit
        # an audit trail — the same claim ought to decide the same way twice —
        # but both deployments behind this project reject the parameter: the
        # chat-latest model accepts only its default, reasoning models take none
        # at all. Sending one fails every call, which is worse than sampling.
        temperature=None,
    )
    return ChatBackend(model, f"azure:{deployment}")


def azure_configured() -> bool:
    """True when the hosted deployment is available — the UI offers it instead
    of Ollama, which only exists on a developer's own machine."""
    return bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))


def get_backend(kind: str = "auto") -> Backend:
    """Resolve a backend, falling back to the rules engine rather than failing."""
    if kind == "mock":
        return MockBackend()
    if kind == "naive":
        return NaiveAgentBackend()
    if kind == "ollama":
        return _ollama_backend()
    if kind == "azure":
        return _azure_backend()
    if kind == "auto" and azure_configured():
        try:
            return _azure_backend()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! azure backend unavailable ({exc.__class__.__name__}), falling back")
    if kind == "auto" and os.environ.get("PETRI_OLLAMA_URL"):
        try:
            return _ollama_backend()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ollama backend unavailable ({exc.__class__.__name__}), falling back")
    return MockBackend()
