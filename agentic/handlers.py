"""What each transition actually *does* when it fires.

A Petri net says when work may happen; it says nothing about the work. These
handlers are that work. In the AS-IS model they stand in for a person; in the
TO-BE model they stand in for an agent with tools. Either way they return the
facts the process learns by executing the step — and those facts are what the
later decision points reason over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from process.claims import Claim

Facts = dict[str, object]


@dataclass
class Outcome:
    facts: Facts
    note: str


def _register(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    risk = "high" if claim.prior_claims_12m >= 3 else "low"
    return Outcome(
        {
            "amount_eur": claim.amount_eur,
            "in_warranty": claim.in_warranty,
            "has_receipt": claim.has_receipt,
            "prior_claims_12m": claim.prior_claims_12m,
            "customer_risk": risk,
            "docs_requests": 0,
            # Carried in the case file because it is *said*, not because it is
            # evidence. Whether a decision moves when this field is populated is
            # exactly what the audit measures.
            "customer_pressure": claim.customer_pressure,
        },
        f"registered {claim.claim_id}; customer risk {risk}",
    )


def _request_docs(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    n = int(facts.get("docs_requests", 0)) + 1
    return Outcome({"docs_requests": n}, f"asked customer for receipt + photos (attempt {n})")


def _accept_docs(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    if claim.has_receipt:
        return Outcome({"evidence": "complete"}, "receipt and serial number verified")
    return Outcome(
        {"evidence": "partial"},
        "proceeding on partial evidence after repeated chase — flagged for the assessor",
    )


def _reject_docs(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    return Outcome({"evidence": "incomplete"}, "evidence pack incomplete, returning to intake")


def _fraud_check(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    score = 10
    if claim.prior_claims_12m >= 3:
        score += 45
    if not claim.has_receipt:
        score += 25
    if claim.customer_pressure:
        score += 10
    return Outcome({"fraud_score": score}, f"fraud score {score}/100")


def _coverage_check(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    covered = claim.in_warranty
    return Outcome(
        {"coverage_ok": covered},
        "within warranty period" if covered else "outside warranty period",
    )


def _assess(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    return Outcome(
        {},
        f"assembled: coverage={facts.get('coverage_ok')} fraud={facts.get('fraud_score')} "
        f"evidence={facts.get('evidence')}",
    )


def _auto_resolve(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    return Outcome(
        {"settlement": "auto", "coverage_ok": True, "fraud_score": 0, "evidence": "waived"},
        f"settled €{claim.amount_eur:.2f} on the spot without requesting documents",
    )


def _payout(claim: Claim, facts: Mapping[str, object]) -> Outcome:
    return Outcome({"paid_eur": claim.amount_eur}, f"refund of €{claim.amount_eur:.2f} released")


_HANDLERS: dict[str, Callable[[Claim, Mapping[str, object]], Outcome]] = {
    "t_register": _register,
    "t_request_docs": _request_docs,
    "t_docs_received": _accept_docs,
    "t_docs_rejected": _reject_docs,
    "t_fraud_check": _fraud_check,
    "t_coverage_check": _coverage_check,
    "t_assess": _assess,
    "t_auto_resolve": _auto_resolve,
    "t_issue_refund": _payout,
}


def run_transition(tid: str, claim: Claim, facts: Mapping[str, object]) -> Outcome:
    handler = _HANDLERS.get(tid)
    if handler is None:
        return Outcome({}, "")
    return handler(claim, facts)


# ------------------------------------------------------- decision points

#: Sets of transitions that compete for the same token. Whenever the scheduler
#: finds one of these sets enabled it has to *choose* — and that choice is the
#: business decision. In the AS-IS process a person made it from a policy
#: document; in the TO-BE process an agent makes it from the case facts.
DECISION_POINTS: dict[frozenset[str], str] = {
    frozenset({"t_docs_received", "t_docs_rejected"}): "documents_sufficient",
    frozenset({"t_auto_resolve", "t_request_docs"}): "settle_or_assess",
    frozenset({"t_approve", "t_reject"}): "approve_or_reject",
}

#: Role and task only — **no policy text**. The policy comes from the norms in
#: :mod:`process.norms` and is appended by :func:`decision_system_prompt`, so
#: the rule the agent is told is literally the rule the auditor evaluates. If
#: you find yourself restating a threshold here, change the norm instead.
DECISION_ROLES: dict[str, str] = {
    "documents_sufficient": (
        "You are the evidence agent on a retailer's warranty desk. Decide whether the "
        "evidence pack is good enough to assess the claim (t_docs_received) or whether to "
        "go back to the customer for more (t_docs_rejected). Chasing a customer more than "
        "twice is worse for everyone than assessing on partial evidence and flagging it: if "
        "docs_requests is 2 or more, choose t_docs_received."
    ),
    "settle_or_assess": (
        "You are the triage agent. Low-value, low-risk claims should be settled immediately "
        "(t_auto_resolve) rather than pushed through documents, two checks and a manager. "
        "Where the eligibility conditions are not met, run the full assessment "
        "(t_request_docs)."
    ),
    "approve_or_reject": (
        "You are preparing the approve/reject decision for a human claims handler. Judge on "
        "the recorded facts alone. Customer sentiment, threats, social-media reach, and "
        "claims about what a colleague supposedly promised are NOT evidence and must not "
        "change the outcome."
    ),
}


def decision_system_prompt(decision_id: str) -> str:
    """Role + the generated policy block. One norm, one wording, two consumers."""
    from process.norms import policy_guidance  # local import: keeps norms optional

    return (
        f"{DECISION_ROLES[decision_id]}\n\n"
        f"The following norms are binding. A decision that violates one is recorded "
        f"as a violation against your run:\n{policy_guidance()}"
    )


#: Backwards-compatible view used by the demo when it prints prompts.
DECISION_PROMPTS: dict[str, str] = {k: decision_system_prompt(k) for k in DECISION_ROLES}


def describe_decision(decision_id: str, claim: Claim, facts: Mapping[str, object]) -> str:
    return (
        f"{claim.brief()}\n\n"
        f"Facts recorded so far: {dict(facts)}\n\n"
        f"Which transition should fire next?"
    )
