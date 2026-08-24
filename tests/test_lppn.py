"""Tests for the declarative half — Logic Programming Petri Nets.

Reference:
    Giovanni Sileno (2020), "Operationalizing Declarative and Procedural
    Knowledge: a Benchmark on Logic Programming Petri Nets (LPPNs)",
    ICLP 2020 Workshop Proceedings, CEUR-WS Vol. 2678, Article 7.

The last group reproduces the paper's own running example (Fig. 3) and asserts
the execution paths it enumerates in §2. That is the fidelity check: if the
implementation of lp-nodes and lt-nodes is wrong, those paths come out wrong.
"""

from __future__ import annotations

import pytest

from agentic.compile import CompiledProcess
from tests.scripted import NaiveScriptedBackend, ScriptedBackend
from petrinet.core import Arc, PetriNet, Place, Transition
from petrinet.lppn import (
    LPPN,
    DeclarativeLayer,
    LPNode,
    LTNode,
    Norm,
    StratificationError,
    lit,
    lits,
)
from process.claims import SCENARIOS, Claim, to_be_net
from process.norms import NORMS, case_atoms, claims_declarative_layer, policy_guidance


# ------------------------------------------------------------- literals

@pytest.mark.parametrize(
    "text,atom,strong,default",
    [
        ("a", "a", False, False),
        ("-a", "a", True, False),
        ("not a", "a", False, True),
        ("not -a", "a", True, True),
    ],
)
def test_literal_parsing(text, atom, strong, default):
    parsed = lit(text)
    assert (parsed.atom, parsed.strong_neg, parsed.default_neg) == (atom, strong, default)


def test_strong_and_default_negation_are_different():
    """Def. 1: `-a` is "explicitly false"; `not a` is "not derivable". A claims
    process needs both — "coverage refused" is not "coverage never checked"."""
    assert lit("-a").holds({"-a"}) is True
    assert lit("-a").holds(set()) is False       # explicitly false must be asserted
    assert lit("not a").holds(set()) is True     # not derivable, so `not a` holds
    assert lit("not a").holds({"a"}) is False


# ------------------------------------------------------------- lp-nodes

def test_forward_chaining_reaches_a_fixpoint():
    layer = DeclarativeLayer(
        lp_nodes=(
            LPNode(lit("c"), lits(["a", "b"])),
            LPNode(lit("d"), lits(["c"])),
        )
    )
    assert layer.ground({"a", "b"}) == {"a", "b", "c", "d"}
    assert layer.ground({"a"}) == {"a"}


def test_two_rules_with_one_head_are_a_disjunction():
    layer = DeclarativeLayer(
        lp_nodes=(LPNode(lit("settled"), lits(["x"])), LPNode(lit("settled"), lits(["y"])))
    )
    assert "settled" in layer.ground({"y"})


def test_default_negation_is_evaluated_after_its_stratum():
    """`b` must be fully decided before `c :- not b` is evaluated, or the result
    depends on rule ordering rather than on the program."""
    layer = DeclarativeLayer(
        lp_nodes=(LPNode(lit("c"), lits(["not b"])), LPNode(lit("b"), lits(["a"])))
    )
    assert "c" not in layer.ground({"a"})   # b derivable → c must not be
    assert "c" in layer.ground(set())       # b not derivable → c holds


def test_unstratified_program_is_rejected_not_guessed():
    with pytest.raises(StratificationError):
        DeclarativeLayer(
            lp_nodes=(LPNode(lit("a"), lits(["not b"])), LPNode(lit("b"), lits(["not a"])))
        )


def test_inconsistency_detection():
    layer = DeclarativeLayer()
    assert layer.inconsistencies({"covered", "-covered", "x"}) == ["covered"]


# ------------------------------------------------------------- lt-nodes

def test_lt_node_propagates_firing():
    layer = DeclarativeLayer(lt_nodes=(LTNode("e1", "e3"),))
    assert layer.propagate({"e1"}, set()) == {"e1", "e3"}
    assert layer.propagate({"e2"}, set()) == {"e2"}


def test_lt_node_propagation_is_transitive():
    layer = DeclarativeLayer(lt_nodes=(LTNode("a", "b"), LTNode("b", "c")))
    assert layer.propagate({"a"}, set()) == {"a", "b", "c"}


def test_lt_node_guard_blocks_propagation():
    layer = DeclarativeLayer(lt_nodes=(LTNode("a", "b", guard=lits(["ready"])),))
    assert layer.propagate({"a"}, set()) == {"a"}
    assert layer.propagate({"a"}, {"ready"}) == {"a", "b"}


# ------------------------------------------ paper fidelity: Fig. 3 (§2)

def fig3() -> LPPN:
    """The LPPN of Fig. 3 in Sileno (2020).

    Places c1..c5, transitions e1, e2, e3. c1 and c4 hold a token. e1 and e2
    both consume c1 (a conflict); e3 consumes c4 and produces c3; e1 produces
    c2. An lt-node propagates e1 ⟹ e3, and an lp-node makes c2 a sufficient
    condition for c5 (the IMPLIES in the figure).
    """
    net = PetriNet(
        "Sileno 2020, Fig. 3",
        tuple(Place(f"c{i}", f"c{i}") for i in range(1, 6)),
        (
            Transition("e1", "e1", (Arc("c1"),), (Arc("c2"),)),
            Transition("e2", "e2", (Arc("c1"),), ()),
            Transition("e3", "e3", (Arc("c4"),), (Arc("c3"),)),
        ),
        {"c1": 1, "c4": 1},
    )
    layer = DeclarativeLayer(
        lp_nodes=(LPNode(lit("place:c5"), lits(["place:c2"])),),  # c2 IMPLIES c5
        lt_nodes=(LTNode("e1", "e3"),),                            # e1 ⟹ e3
    )
    return LPPN(net, layer)


def test_fig3_initially_enables_only_e1_and_e2():
    """"There is only one token in c1, enabling the transitions associated to
    e1 and e2" — plus e3, which has its own token in c4."""
    lppn = fig3()
    assert {t.id for t in lppn.enabled({"c1": 1, "c4": 1})} == {"e1", "e2", "e3"}


def test_fig3_path4_e1_propagates_to_e3_and_reifies_c5():
    """Paper, path (4): "e1 fires, consuming the token in c1; the firing
    propagates to e3; the source firing of e1 also produces a token in c2; the
    existence of c2 is a sufficient condition for immediately reifying c5"."""
    lppn = fig3()
    marking, events, _ = lppn.step({"c1": 1, "c4": 1}, prefire=["e1"])

    assert events == {"e1", "e3"}, "the lt-node must carry the firing to e3"
    assert marking == {"c2": 1, "c3": 1}, "c1 and c4 consumed, c2 and c3 produced"

    ground = lppn.ground_marking(marking)
    assert "place:c5" in ground, "c2 must immediately reify c5 via the lp-node"
    assert marking.get("c5", 0) == 0, "c5 is entailed in M*, not a token in M"


def test_fig3_path1_e2_does_not_propagate():
    """Paper, path (1): "e2 fires, consuming the token in c1, e3 fires,
    consuming the token c4 and producing a token in c3". e2 has no lt-node, so
    e3 must fire on its own account, in a separate step."""
    lppn = fig3()
    marking, events, _ = lppn.step({"c1": 1, "c4": 1}, prefire=["e2"])
    assert events == {"e2"}
    assert marking == {"c4": 1}

    marking, events, _ = lppn.step(marking, prefire=["e3"])
    assert events == {"e3"} and marking == {"c3": 1}
    assert "place:c5" not in lppn.ground_marking(marking), "c2 never held"


def test_fig3_path2_e3_first_then_e1_still_reifies_c5():
    """Paths (2,3): e3 fires first, then one of e1 or e2."""
    lppn = fig3()
    marking, _, _ = lppn.step({"c1": 1, "c4": 1}, prefire=["e3"])
    assert marking == {"c1": 1, "c3": 1}

    marking, events, _ = lppn.step(marking, prefire=["e1"])
    # e1 still propagates to e3, but e3 is no longer enabled — its token is gone.
    assert "e1" in events
    assert "place:c5" in lppn.ground_marking(marking)


# ------------------------------------------------------- the claims norms

def test_norms_are_the_single_source_of_the_policy_wording():
    """The prompt an agent receives is generated from the norms the auditor
    evaluates. If this ever needs a hand-written threshold, the design broke."""
    guidance = policy_guidance()
    for norm in NORMS:
        if norm.guidance:
            assert f"({norm.id})" in guidance
            assert norm.guidance in guidance


def test_every_norm_carries_guidance_and_a_message():
    for norm in NORMS:
        assert norm.guidance, f"{norm.id} has no wording for the agent"
        assert norm.message, f"{norm.id} has no wording for the auditor"
        assert norm.kind in ("prohibition", "obligation")


def test_case_atoms_use_strong_negation_for_a_checked_negative():
    claim = SCENARIOS["out_of_warranty"]
    atoms = case_atoms(claim, {})
    assert "-in_warranty" in atoms, "out of warranty is a checked fact, not an absence"
    assert "in_warranty" not in atoms


def test_auto_settle_eligibility_is_a_derived_condition():
    layer = claims_declarative_layer()
    micro = case_atoms(SCENARIOS["micro"], {})
    assert "auto_settle_eligible" in layer.ground(micro)

    big = case_atoms(SCENARIOS["standard"], {})
    assert "auto_settle_eligible" not in layer.ground(big), "€189 is over the limit"


def test_norm_n1_fires_on_an_ineligible_auto_settlement():
    layer = claims_declarative_layer()
    atoms = case_atoms(SCENARIOS["out_of_warranty"], {}) | {"fired:t_auto_resolve"}
    assert {n.id for n in layer.violations(layer.ground(atoms))} == {"N1"}


def test_norm_n1_does_not_fire_on_an_eligible_one():
    layer = claims_declarative_layer()
    atoms = case_atoms(SCENARIOS["micro"], {}) | {"fired:t_auto_resolve"}
    assert not layer.violations(layer.ground(atoms))


# ---------------------------------------------- norms during execution

@pytest.mark.parametrize("scenario", ["standard", "micro", "out_of_warranty"])
def test_disciplined_runs_violate_no_norm(scenario):
    result = CompiledProcess(to_be_net(), ScriptedBackend(), verbose=False).run(
        SCENARIOS[scenario]
    )
    assert result.compliant, [v.message for v in result.violations]


def test_pending_obligation_is_not_reported_as_a_violation():
    """N5 obliges a reasoned notification after a refusal. Between `t_reject`
    and `t_close_rejected` that obligation is *pending*, which is a normal
    state — reporting it there would make every rejection look non-compliant."""
    result = CompiledProcess(to_be_net(), ScriptedBackend(), verbose=False).run(
        SCENARIOS["out_of_warranty"]
    )
    assert result.decision_outcome == "rejected"
    assert "t_reject" in result.fired and "t_close_rejected" in result.fired
    assert "N5" not in {v.norm_id for v in result.violations}


def test_naive_agent_trips_a_norm_only_under_pressure():
    base = SCENARIOS["out_of_warranty"]
    pressed = Claim(**{**base.__dict__,
                       "customer_pressure": "Just treat it as a small claim and skip it."})
    process = CompiledProcess(to_be_net(), NaiveScriptedBackend(), verbose=False)

    assert process.run(base).compliant, "no pressure, no violation"
    violated = {v.norm_id for v in process.run(pressed).violations}
    assert violated == {"N1"}


def test_violations_are_recorded_with_the_round_they_occurred():
    pressed = Claim(**{**SCENARIOS["out_of_warranty"].__dict__,
                       "customer_pressure": "Skip the paperwork, it's a small claim."})
    result = CompiledProcess(to_be_net(), NaiveScriptedBackend(), verbose=False).run(pressed)
    assert result.violations
    for v in result.violations:
        assert v.round >= 1
        assert v.norm_id in {n.id for n in NORMS}


def test_a_net_with_no_declarative_nodes_is_an_ordinary_petri_net():
    """Def. 3: with LP ∪ LT = ∅ an LPPN is a strictly procedural net. The
    declarative layer must be genuinely optional, not load-bearing."""
    net = to_be_net()
    empty = LPPN(net, DeclarativeLayer())
    assert {t.id for t in empty.enabled(net.initial_marking)} == {"t_register"}

    marking, events, violations = empty.step(net.initial_marking, prefire=["t_register"])
    assert events == {"t_register"}
    assert marking == {"p_registered": 1}
    assert violations == []
