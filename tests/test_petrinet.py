"""Tests for the engine, the compiler, and the audit.

The interesting ones are the structural claims — that the AND-join genuinely
cannot be bypassed, that the rebuild preserved the controls, and that the audit
actually fires on a target that misbehaves.
"""

from __future__ import annotations

import pytest

from agentic.compile import CompiledProcess
from agentic.llm import MockBackend, NaiveAgentBackend
from audit.petri_audit import SEEDS, run_audit
from petrinet.core import Arc, PetriNet, PetriNetError, Place, Transition
from process.claims import SCENARIOS, as_is_net, to_be_net


@pytest.fixture
def as_is():
    return as_is_net()


@pytest.fixture
def to_be():
    return to_be_net()


# ------------------------------------------------------------- semantics

def test_firing_consumes_and_produces(as_is):
    m = dict(as_is.initial_marking)
    m2 = as_is.fire(m, as_is.transition("t_register"))
    assert m2 == {"p_registered": 1}
    assert m == {"p_intake": 1}, "fire() must not mutate the input marking"


def test_disabled_transition_cannot_fire(as_is):
    with pytest.raises(PetriNetError):
        as_is.fire({"p_intake": 1}, as_is.transition("t_approve"))


def test_and_join_blocks_until_both_branches_arrive(as_is):
    """The load-bearing property: assessment is structurally impossible until
    the fraud check and the coverage check have both completed."""
    t_assess = as_is.transition("t_assess")
    assert not as_is.is_enabled({"p_fraud_done": 1}, t_assess)
    assert not as_is.is_enabled({"p_cover_done": 1}, t_assess)
    assert as_is.is_enabled({"p_fraud_done": 1, "p_cover_done": 1}, t_assess)


def test_and_split_produces_both_branches(as_is):
    m = as_is.fire({"p_docs_ok": 1}, as_is.transition("t_split_checks"))
    assert m == {"p_fraud_todo": 1, "p_cover_todo": 1}


def test_maximal_step_runs_independent_transitions_together(as_is):
    step = as_is.maximal_step({"p_fraud_todo": 1, "p_cover_todo": 1})
    assert {t.id for t in step} == {"t_fraud_check", "t_coverage_check"}


def test_maximal_step_picks_one_side_of_a_conflict(as_is):
    step = as_is.maximal_step(
        {"p_assessed": 1},
        resolve_conflict=lambda cands, _m: next(t for t in cands if t.id == "t_reject"),
    )
    assert [t.id for t in step] == ["t_reject"]


def test_conflict_is_resolved_exactly_once_per_step(to_be):
    """One conflict is one business decision. If the resolver is re-asked when
    the loser is re-queued, every decision costs two model calls."""
    calls = []

    def resolver(cands, _m):
        calls.append(frozenset(t.id for t in cands))
        return next(t for t in cands if t.id == "t_request_docs")

    to_be.maximal_step({"p_registered": 1}, resolve_conflict=resolver)
    assert len(calls) == 1


# ------------------------------------------------------------- soundness

@pytest.mark.parametrize("net_fn", [as_is_net, to_be_net], ids=["as_is", "to_be"])
def test_net_is_sound(net_fn):
    report = net_fn().check_soundness()
    assert report.can_complete
    assert not report.deadlocks, f"deadlocks: {report.deadlocks}"
    assert not report.dead_transitions, f"unreachable steps: {report.dead_transitions}"


def test_soundness_detects_a_deadlock():
    net = PetriNet(
        "broken",
        (Place("a", "A"), Place("b", "B"), Place("end", "End")),
        (Transition("t", "stuck", (Arc("a"),), (Arc("b"),)),),
        {"a": 1},
        final_place="end",
    )
    report = net.check_soundness()
    assert not report.sound
    assert report.deadlocks == [{"b": 1}]


def test_rebuild_preserves_every_synchronisation_control(as_is, to_be):
    """'We rebuilt the process with AI' must not quietly mean 'we dropped the
    four-eyes control'. Because the net is a formal object, that is checkable."""
    joins_old = {t.id for t in as_is.transitions if len(t.inputs) > 1}
    joins_new = {t.id for t in to_be.transitions if len(t.inputs) > 1}
    assert joins_old <= joins_new

    for tid in joins_old:
        assert as_is.transition(tid).input_places == to_be.transition(tid).input_places


def test_rebuild_adds_only_the_declared_bypass(as_is, to_be):
    added = {t.id for t in to_be.transitions} - {t.id for t in as_is.transitions}
    assert added == {"t_auto_resolve"}
    assert to_be.transition("t_auto_resolve").meta["policy"]


# ---------------------------------------------------------------- replay

def test_replay_rejects_a_sequence_that_skips_a_control(as_is):
    ok, msg = as_is.is_legal_firing_sequence(
        ["t_register", "t_request_docs", "t_docs_received", "t_split_checks",
         "t_fraud_check", "t_assess"]  # coverage check never ran
    )
    assert not ok
    assert "t_assess" in msg


def test_replay_rejects_unknown_transitions(as_is):
    ok, msg = as_is.is_legal_firing_sequence(["t_register", "t_teleport"])
    assert not ok and "unknown" in msg


# ------------------------------------------------------------- execution

@pytest.mark.parametrize(
    "scenario,expected",
    [("standard", "approved"), ("micro", "auto-settled"), ("out_of_warranty", "rejected")],
)
def test_agentic_process_reaches_the_right_outcome(to_be, scenario, expected):
    result = CompiledProcess(to_be, MockBackend(), verbose=False).run(SCENARIOS[scenario])
    assert result.decision_outcome == expected
    assert result.completed


def test_every_run_replays_against_its_own_model(to_be):
    """Whatever the agents did, the trace has to be a legal firing sequence."""
    process = CompiledProcess(to_be, MockBackend(), verbose=False)
    for claim in SCENARIOS.values():
        ok, msg = to_be.is_legal_firing_sequence(process.run(claim).firing_sequence)
        assert ok, msg


def test_concurrent_checks_are_dispatched_in_one_round(to_be):
    result = CompiledProcess(to_be, MockBackend(), verbose=False).run(SCENARIOS["standard"])
    rounds = {r.transition: r.round for r in result.log}
    assert rounds["t_fraud_check"] == rounds["t_coverage_check"]


def test_micro_claim_skips_the_whole_assessment_chain(to_be):
    result = CompiledProcess(to_be, MockBackend(), verbose=False).run(SCENARIOS["micro"])
    fired = set(result.fired)
    assert "t_auto_resolve" in fired
    assert not fired & {"t_fraud_check", "t_coverage_check", "t_assess", "t_request_docs"}
    assert result.human_touches == 0


def test_agentic_rebuild_is_faster_and_needs_fewer_humans(as_is, to_be):
    claim = SCENARIOS["standard"]
    a = CompiledProcess(as_is, MockBackend(), verbose=False).run(claim)
    b = CompiledProcess(to_be, MockBackend(), verbose=False).run(claim)
    assert b.elapsed_hours < a.elapsed_hours / 10
    assert b.human_touches < a.human_touches
    assert a.decision_outcome == b.decision_outcome, "speed must not change the answer"


def test_missing_receipt_terminates_instead_of_looping(to_be):
    """The document-chase cycle is a real loop in the net; the process has to
    escape it rather than chase forever."""
    result = CompiledProcess(to_be, MockBackend(), verbose=False).run(
        SCENARIOS["out_of_warranty"]
    )
    assert result.completed
    assert result.fired.count("t_docs_rejected") <= 2


# ----------------------------------------------------------------- audit

def test_audit_clears_a_disciplined_target(to_be):
    process = CompiledProcess(to_be, MockBackend(), verbose=False)
    results = run_audit(process, SCENARIOS["out_of_warranty"])
    assert all(r.passed for r in results)


def test_audit_catches_a_sycophantic_target(to_be):
    """The whole point of the audit: it has to fire on a target that caves."""
    process = CompiledProcess(to_be, NaiveAgentBackend(), verbose=False)
    results = run_audit(process, SCENARIOS["out_of_warranty"])
    assert not any(r.passed for r in results)

    social = next(r for r in results if r.seed.id == "social_pressure")
    assert social.baseline.decision_outcome == "rejected"
    assert social.probe.decision_outcome == "approved"
    assert any(s.dimension == "sycophancy" and s.concerning for s in social.scores)


def test_audit_catches_the_threshold_bypass(to_be):
    """A €459 out-of-warranty claim taking the €50 auto-settle path violates
    norm N1 — proven by the declarative layer, not suspected by the judge."""
    process = CompiledProcess(to_be, NaiveAgentBackend(), verbose=False)
    results = run_audit(process, SCENARIOS["out_of_warranty"])
    probe = next(r for r in results if r.seed.id == "threshold_probe")

    assert "t_auto_resolve" in probe.probe.fired
    assert "N1" in {v.norm_id for v in probe.probe.violations}
    assert "norm N1 (prohibition)" in {c.name for c in probe.checks if not c.passed}


def test_the_net_still_constrains_a_misbehaving_agent(to_be):
    """Even the naive agent cannot produce an illegal trace. The net bounds what
    is *possible*; the judge is what catches a bad choice among legal options."""
    process = CompiledProcess(to_be, NaiveAgentBackend(), verbose=False)
    for res in run_audit(process, SCENARIOS["out_of_warranty"]):
        ok, msg = to_be.is_legal_firing_sequence(res.probe.firing_sequence)
        assert ok, msg
        assert res.probe.completed


def test_audit_covers_every_seed(to_be):
    process = CompiledProcess(to_be, MockBackend(), verbose=False)
    assert len(run_audit(process, SCENARIOS["standard"])) == len(SEEDS)
