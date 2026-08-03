"""Compile a Petri net into an executable LangGraph.

LangGraph does not have token semantics — it has nodes and edges. So the
compiler does not flatten the net into a chain of nodes (that would throw away
exactly the properties worth keeping). Instead it builds a **token-game
interpreter** as a graph:

    START ──▶ scheduler ──Send──▶ t_fraud_check   ──┐
                  │      ──Send──▶ t_coverage_check ─┤
                  │                                  │
                  ◀──────────────────────────────────┘
                  │
                 END   (when no transition is enabled)

The scheduler is the only thing that touches the marking's input side: each
round it finds the enabled transitions, resolves any conflict between them
(that call is the business decision — an LLM makes it), atomically consumes
their input tokens, and fans out one ``Send`` per surviving transition. Each
transition node does its work and produces its output tokens. Control returns
to the scheduler and the cycle repeats.

Two properties fall out of this that a hand-drawn agent graph doesn't get:

* **Real concurrency.** Fraud and coverage checks are dispatched in the same
  superstep because the net says the tokens are there for both — not because
  someone remembered to parallelise them.
* **A synchronisation guarantee that cannot be bypassed.** ``t_assess``
  consumes from two places, so no amount of agent enthusiasm makes it fire
  before both checks have landed. The control is structural, not prompted.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Sequence, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agentic import handlers
from agentic.llm import Backend, Judgement
from petrinet.core import Marking, PetriNet, Transition
from petrinet.lppn import DeclarativeLayer, Norm
from process.claims import Claim

MAX_ROUNDS = 40


# ------------------------------------------------------------- reducers

def merge_marking(current: Marking | None, delta: Marking | None) -> Marking:
    """Apply a token delta. Every write to the marking is a ``{place: ±n}`` map,
    which is what makes concurrent producers safe to merge."""
    out = dict(current or {})
    for place, change in (delta or {}).items():
        out[place] = out.get(place, 0) + change
        if out[place] <= 0:
            out.pop(place)
    return out


def merge_facts(current: dict | None, update: dict | None) -> dict:
    return {**(current or {}), **(update or {})}


class ProcessState(TypedDict, total=False):
    claim: Any
    marking: Annotated[Marking, merge_marking]
    facts: Annotated[dict, merge_facts]
    log: Annotated[list, operator.add]
    fired: Annotated[list, operator.add]
    elapsed_hours: Annotated[float, operator.add]
    rounds: Annotated[int, operator.add]
    violations: Annotated[list, operator.add]
    dispatch: list


@dataclass
class StepRecord:
    round: int
    transition: str
    label: str
    actor: str
    autonomy: str
    note: str
    hours: float
    marking_after: Marking = field(default_factory=dict)


@dataclass
class ViolationRecord:
    """A norm found violated by the ground marking after a step."""

    round: int
    norm_id: str
    kind: str
    message: str


@dataclass
class DecisionRecord:
    round: int
    decision_id: str
    options: list[str]
    judgement: Judgement


def duration_hours(t: Transition) -> float:
    """Wall-clock cost of firing this transition, in hours.

    The AS-IS model bills hands-on ``hours`` *plus* the ``queue_h`` a case sits
    in someone's tray — which is where the cycle time actually goes. The TO-BE
    model bills agent latency in ``seconds``; a human-in-the-loop step still
    carries a realistic wait.
    """
    if "seconds" in t.meta:
        return float(t.meta["seconds"]) / 3600.0
    return float(t.meta.get("hours", 0)) + float(t.meta.get("queue_h", 0))


def actor_of(t: Transition) -> str:
    return str(t.meta.get("agent") or t.meta.get("owner") or "—")


# -------------------------------------------------------------- compiler

class CompiledProcess:
    def __init__(self, net: PetriNet, backend: Backend, verbose: bool = True,
                 declarative: DeclarativeLayer | None = None, atom_fn=None):
        self.net = net
        self.backend = backend
        self.verbose = verbose
        # The declarative half (Sileno 2020). Optional: with it absent this is a
        # strictly procedural net, which Def. 3 says is just an ordinary Petri net.
        if declarative is None or atom_fn is None:
            from process.norms import case_atoms, claims_declarative_layer

            declarative = declarative or claims_declarative_layer()
            atom_fn = atom_fn or case_atoms
        self.declarative = declarative
        self.atom_fn = atom_fn
        self.decisions: list[DecisionRecord] = []
        self.graph = self._build()

    # -- the declarative half ------------------------------------------------

    def ground(self, marking: Marking, claim: Claim, facts: dict,
               fired: list[str]) -> set[str]:
        """Source marking + case facts + event history → ground marking M*.

        Step 1 of the LPPN execution cycle. Everything the state entails, not
        merely what a token is sitting on.
        """
        atoms = {f"place:{p}" for p, n in marking.items() if n}
        atoms |= {f"fired:{t}" for t in fired}
        atoms |= self.atom_fn(claim, facts)
        return self.declarative.ground(atoms)

    # -- the business decision at a conflict --------------------------------

    def _resolve(
        self, candidates: Sequence[Transition], claim: Claim, facts: dict, rnd: int
    ) -> Transition:
        by_id = {t.id: t for t in candidates}
        key = frozenset(by_id)
        decision_id = handlers.DECISION_POINTS.get(key)
        if decision_id is None:
            # Undeclared conflict — deterministic tie-break so runs stay replayable.
            return sorted(candidates, key=lambda t: t.id)[0]

        judgement = self.backend.decide(
            decision_id=decision_id,
            system=handlers.decision_system_prompt(decision_id),
            user=handlers.describe_decision(decision_id, claim, facts),
            options=sorted(by_id),
            facts=facts,
        )
        self.decisions.append(DecisionRecord(rnd, decision_id, sorted(by_id), judgement))
        if self.verbose:
            print(f"    ? {decision_id}: {judgement.line()}")
        return by_id[judgement.choice]

    # -- nodes ---------------------------------------------------------------

    def _scheduler(self, state: ProcessState) -> dict:
        marking = state.get("marking", {})
        rnd = state.get("rounds", 0) + 1
        if rnd > MAX_ROUNDS:
            return {"dispatch": [], "rounds": 1}

        claim: Claim = state["claim"]  # type: ignore[typeddict-item]
        facts = dict(state.get("facts", {}))

        step = self.net.maximal_step(
            marking,
            resolve_conflict=lambda cands, _m: self._resolve(cands, claim, facts, rnd),
        )

        # Evaluate the declarative half against the state the previous round
        # produced. This is the auditing hook: norms are checked continuously
        # against the ground marking, not reconstructed afterwards from a log.
        #
        # Prohibitions and obligations are *not* checked at the same moments,
        # and conflating them produces false positives. A prohibition ("must not
        # auto-settle an ineligible claim") is violated the instant its state is
        # reached and can never be undone, so it is checked every round. An
        # obligation ("a refusal must be communicated") is only violated if the
        # process stops without discharging it — until then it is merely
        # pending, which is a normal state to be in, not a finding.
        terminal = not step
        seen = {v.norm_id for v in state.get("violations", [])}
        ground = self.ground(marking, claim, facts, state.get("fired", []))
        fresh = [
            ViolationRecord(rnd - 1, n.id, n.kind, n.message)
            for n in self.declarative.violations(ground)
            if n.id not in seen and (terminal or n.kind != "obligation")
        ]
        if fresh and self.verbose:
            for v in fresh:
                print(f"    ⚠ VIOLATION {v.norm_id}: {v.message}")

        if terminal:
            return {"dispatch": [], "rounds": 1, "violations": fresh}

        # Consume every chosen transition's input tokens in one atomic write,
        # before any of them runs. Firing is consume-then-produce; splitting it
        # across the scheduler and the transition nodes is what makes it safe to
        # run the transitions concurrently.
        consumed: Marking = {}
        for t in step:
            for arc in t.inputs:
                consumed[arc.place] = consumed.get(arc.place, 0) - arc.weight

        cost = max(duration_hours(t) for t in step)
        if self.verbose:
            names = ", ".join(t.label for t in step)
            para = " ‖ " if len(step) > 1 else ""
            print(f"  [{rnd:>2}] fire{para}: {names}")

        return {
            "marking": consumed,
            "dispatch": [t.id for t in step],
            "rounds": 1,
            "elapsed_hours": cost,
            "violations": fresh,
        }

    def _make_transition_node(self, t: Transition):
        def node(payload: dict) -> dict:
            claim: Claim = payload["claim"]
            facts: dict = payload["facts"]
            outcome = handlers.run_transition(t.id, claim, facts)

            produced: Marking = {}
            for arc in t.outputs:
                produced[arc.place] = produced.get(arc.place, 0) + arc.weight

            record = StepRecord(
                round=payload["round"],
                transition=t.id,
                label=t.label,
                actor=actor_of(t),
                autonomy=str(t.meta.get("autonomy", "human")),
                note=outcome.note,
                hours=duration_hours(t),
            )
            if self.verbose and outcome.note:
                print(f"       · {t.id}: {outcome.note}")
            return {
                "marking": produced,
                "facts": outcome.facts,
                "log": [record],
                "fired": [t.id],
            }

        return node

    def _fan_out(self, state: ProcessState):
        dispatch = state.get("dispatch") or []
        if not dispatch:
            return END
        payload_base = {
            "claim": state["claim"],  # type: ignore[typeddict-item]
            "facts": dict(state.get("facts", {})),
            "round": state.get("rounds", 0),
        }
        return [Send(tid, dict(payload_base)) for tid in dispatch]

    def _build(self):
        builder = StateGraph(ProcessState)
        builder.add_node("scheduler", self._scheduler)
        for t in self.net.transitions:
            builder.add_node(t.id, self._make_transition_node(t))
            builder.add_edge(t.id, "scheduler")
        builder.add_edge(START, "scheduler")
        builder.add_conditional_edges(
            "scheduler",
            self._fan_out,
            [t.id for t in self.net.transitions] + [END],
        )
        return builder.compile()

    # -- run -----------------------------------------------------------------

    def run(self, claim: Claim) -> "RunResult":
        self.decisions = []
        final = self.graph.invoke(
            {
                "marking": dict(self.net.initial_marking),
                "claim": claim,
                "facts": {},
                "log": [],
                "fired": [],
                "elapsed_hours": 0.0,
                "rounds": 0,
                "violations": [],
            },
            {"recursion_limit": 4 * MAX_ROUNDS},
        )
        return RunResult(
            net=self.net,
            claim=claim,
            marking=final.get("marking", {}),
            facts=final.get("facts", {}),
            log=sorted(final.get("log", []), key=lambda r: (r.round, r.transition)),
            fired=final.get("fired", []),
            elapsed_hours=final.get("elapsed_hours", 0.0),
            violations=final.get("violations", []),
            decisions=list(self.decisions),
            backend=self.backend.name,
        )


@dataclass
class RunResult:
    net: PetriNet
    claim: Claim
    marking: Marking
    facts: dict
    log: list[StepRecord]
    fired: list[str]
    elapsed_hours: float
    violations: list[ViolationRecord]
    decisions: list[DecisionRecord]
    backend: str

    @property
    def completed(self) -> bool:
        return bool(self.net.final_place) and self.marking.get(self.net.final_place, 0) > 0

    @property
    def firing_sequence(self) -> list[str]:
        """The recorded run flattened into a sequence the model can replay.

        Concurrent transitions are serialised in round order — any interleaving
        of a legal concurrent step is itself a legal firing sequence, so this is
        a faithful linearisation, not an approximation.
        """
        return [r.transition for r in self.log]

    @property
    def compliant(self) -> bool:
        """Did the run pass through no state that violates a norm?"""
        return not self.violations

    @property
    def decision_outcome(self) -> str:
        """The customer-visible result — the thing the audit diffs."""
        fired = set(self.fired)
        if "t_auto_resolve" in fired:
            return "auto-settled"
        if "t_approve" in fired:
            return "approved"
        if "t_reject" in fired:
            return "rejected"
        return "unresolved"

    @property
    def human_touches(self) -> int:
        return sum(1 for r in self.log if r.autonomy != "auto")

    @property
    def handoffs(self) -> int:
        """Number of times the case changed hands between actors."""
        actors = [r.actor for r in self.log]
        return sum(1 for a, b in zip(actors, actors[1:]) if a != b)
