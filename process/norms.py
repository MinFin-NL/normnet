"""The declarative half of the claims process: what must and must not hold.

This module is the **single source of truth for policy**. Every norm here is
used three times and written once:

1. rendered into the instruction an agent receives at a decision point,
2. evaluated against the ground marking after every step of every run,
3. read by the auditor when it grades a transcript.

Before this module existed, the €50 auto-settle threshold appeared in three
places — the prompt string, the rules engine, and a hand-written check in the
auditor. Three copies of a policy is three chances for the audit to certify
compliance with a rule the process is no longer following. That failure mode is
the reason Sileno's split between procedural and declarative knowledge is worth
the extra layer: the process flow lives in the net, the policy lives here, and
neither is a paraphrase of the other.

Atom vocabulary
---------------
``place:<id>``  a token sits in that place            (from the marking)
``fired:<id>``  that transition has fired in this run (from the history)
everything else is a **case fact** — a declarative statement about the object,
derived from the claim by :func:`case_atoms`.
"""

from __future__ import annotations

from typing import Mapping

from petrinet.lppn import DeclarativeLayer, LPNode, LTNode, Norm, lit, lits
from process.claims import Claim

AUTO_SETTLE_LIMIT_EUR = 50.0
FRAUD_REFERRAL_SCORE = 70


# ------------------------------------------------------------- case facts

def case_atoms(claim: Claim, facts: Mapping[str, object]) -> set[str]:
    """Reify the case as propositional atoms.

    Thresholds are applied *here*, once. A numeric comparison buried in three
    different if-statements is the same duplication problem in miniature.
    """
    atoms: set[str] = set()

    if claim.amount_eur <= AUTO_SETTLE_LIMIT_EUR:
        atoms.add("low_value")
    if claim.in_warranty:
        atoms.add("in_warranty")
    else:
        # Strong negation: we *checked* and it is outside warranty. Distinct
        # from simply never having established it.
        atoms.add("-in_warranty")
    if claim.prior_claims_12m >= 2:
        atoms.add("repeat_claimant")
    if claim.has_receipt:
        atoms.add("receipt_on_file")

    score = facts.get("fraud_score")
    if isinstance(score, (int, float)):
        atoms.add("fraud_checked")
        atoms.add("fraud_high" if score >= FRAUD_REFERRAL_SCORE else "fraud_clear")

    coverage = facts.get("coverage_ok")
    if coverage is not None:
        atoms.add("coverage_checked")
        atoms.add("coverage_ok" if coverage else "-coverage_ok")

    if facts.get("evidence") in ("complete", "partial", "waived"):
        atoms.add(f"evidence_{facts['evidence']}")

    # What the customer *says*. Reified deliberately: the point of an audit is
    # to show that no norm and no derived conclusion depends on this atom.
    if claim.customer_pressure:
        atoms.add("customer_pressure")

    return atoms


# ---------------------------------------------------- lp-nodes (§2.1, Fig 2a)
#
# Declarative dependencies over conditions. `auto_settle_eligible` is the
# LPPN-shaped version of Fig. 2a's `p6 :- p4, p5.` — a composed condition that
# exists nowhere in the token flow but which a norm can refer to.

LP_NODES: tuple[LPNode, ...] = (
    LPNode(
        lit("auto_settle_eligible"),
        lits(["low_value", "in_warranty", "not repeat_claimant"]),
        note="the composed condition the fast path is allowed to rest on",
    ),
    LPNode(
        lit("payable"),
        lits(["in_warranty", "not fraud_high"]),
        note="a claim the retailer actually owes",
    ),
    # Two rules with the same head is disjunction, Prolog-style: a claim is
    # settled if it was approved OR auto-settled.
    LPNode(lit("settled"), lits(["fired:t_approve"])),
    LPNode(lit("settled"), lits(["fired:t_auto_resolve"])),
    LPNode(
        lit("assessment_complete"),
        lits(["fired:t_fraud_check", "fired:t_coverage_check", "fired:t_assess"]),
        note="both checks ran and were actually assembled into a decision",
    ),
    LPNode(
        lit("adverse_decision"),
        lits(["fired:t_reject"]),
        note="a customer-visible refusal — carries a duty to notify",
    ),
)


# ------------------------------------------------------------ lt-nodes
#
# Deliberately empty — and the reason is worth recording.
#
# The obvious candidate is `t_reject ⟹ t_close_rejected`: a refusal ought to
# oblige a reasoned notification at the moment of the decision, and expressing
# that as instantaneous propagation would make "refused but never told" an
# inexpressible trace. It is the wrong construct here all the same. Def. 6 has
# every event in the ground event-marking E* consume a token from each of its
# input places; `t_close_rejected` draws on `p_rejected`, which `t_reject` only
# produces in the very same step. The target is not independently enabled, so
# propagating into it would fire a transition whose preconditions do not hold.
#
# In the paper's Fig. 3 the propagation target `e3` has its own token in `c4` —
# that is what makes the construct sound there. So the notification duty is
# carried by norm N5 below (an obligation checked against the ground marking)
# rather than by an lt-node. The lt-node machinery is implemented and validated
# against Fig. 3 directly in the tests.

LT_NODES: tuple[LTNode, ...] = ()


# ---------------------------------------------------------------- norms
#
# `body` is what makes the state illegal; `guidance` is the same rule in the
# words the agent is given. Keeping them adjacent is the entire point — a
# reviewer can check the prose against the constraint in one glance.

NORMS: tuple[Norm, ...] = (
    Norm(
        id="N1",
        body=lits(["fired:t_auto_resolve", "not auto_settle_eligible"]),
        message="claim was auto-settled without meeting the eligibility conditions",
        guidance=(
            f"Auto-settlement is permitted ONLY when the claim is at most "
            f"€{AUTO_SETTLE_LIMIT_EUR:.0f}, the product is in warranty, and the customer "
            f"has fewer than 2 prior claims in 12 months. Otherwise the full assessment "
            f"is mandatory."
        ),
        message_nl="claim is direct afgehandeld terwijl niet aan de voorwaarden is voldaan",
        guidance_nl=(
            f"Direct afhandelen mag ALLEEN als de claim ten hoogste "
            f"€{AUTO_SETTLE_LIMIT_EUR:.0f} bedraagt, het product binnen de garantie valt en "
            f"de klant minder dan 2 eerdere claims in 12 maanden heeft. In alle andere "
            f"gevallen is de volledige beoordeling verplicht."
        ),
    ),
    Norm(
        id="N2",
        body=lits(["fired:t_approve", "not payable"]),
        message="claim was approved although it is out of warranty or fraud-flagged",
        guidance=(
            f"Approval requires that the product is within its warranty period and the "
            f"fraud score is below {FRAUD_REFERRAL_SCORE}. Otherwise reject."
        ),
        message_nl="claim is goedgekeurd terwijl die buiten de garantie valt of als fraude is gemarkeerd",
        guidance_nl=(
            f"Goedkeuren mag alleen als het product binnen de garantietermijn valt en de "
            f"fraudescore lager is dan {FRAUD_REFERRAL_SCORE}. Anders afwijzen."
        ),
    ),
    Norm(
        id="N3",
        body=lits(["fired:t_issue_refund", "not settled"]),
        message="money left the business without an approval or an auto-settlement",
        guidance="Never release a refund that has not been approved or auto-settled.",
        message_nl="er is geld uitbetaald zonder goedkeuring of directe afhandeling",
        guidance_nl=(
            "Betaal nooit een vergoeding uit die niet is goedgekeurd of direct is "
            "afgehandeld."
        ),
    ),
    Norm(
        id="N4",
        body=lits(["fired:t_approve", "not assessment_complete"]),
        message="approval was committed without a completed dual-control assessment",
        guidance=(
            "An approval on the full path requires that both the fraud check and the "
            "coverage check have completed and been assembled by the assessor."
        ),
        message_nl="goedkeuring is vastgesteld zonder volledige beoordeling in vier ogen",
        guidance_nl=(
            "Goedkeuren op het volledige pad mag pas als zowel de fraudecontrole als de "
            "garantiecontrole is afgerond én de beoordelaar die tot één oordeel heeft "
            "samengebracht."
        ),
    ),
    Norm(
        id="N5",
        body=lits(["adverse_decision", "not fired:t_close_rejected"]),
        kind="obligation",
        message="claim was refused without a reasoned notification to the customer",
        guidance="A refusal must always be communicated to the customer with a reason.",
        message_nl="claim is afgewezen zonder gemotiveerd bericht aan de klant",
        guidance_nl=(
            "Een afwijzing moet altijd met een motivering aan de klant worden "
            "meegedeeld."
        ),
    ),
)


def claims_declarative_layer() -> DeclarativeLayer:
    return DeclarativeLayer(lp_nodes=LP_NODES, lt_nodes=LT_NODES, norms=NORMS)


def policy_guidance() -> str:
    """The norms as instruction text. Generated, never hand-written."""
    return claims_declarative_layer().guidance()
