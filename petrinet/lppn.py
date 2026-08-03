"""Logic Programming Petri Nets — the declarative half.

Implements a propositional LPPN after:

    Giovanni Sileno (2020). "Operationalizing Declarative and Procedural
    Knowledge: a Benchmark on Logic Programming Petri Nets (LPPNs)."
    ICLP 2020 Workshop Proceedings, CEUR-WS Vol. 2678, Article 7.
    Informatics Institute, University of Amsterdam. CC BY 4.0.
    https://pure.uva.nl/ws/files/63279071/paper7.pdf

Why this matters for automating a process with LLMs: a plain Petri net carries
only **procedural** knowledge — the causal mechanism, what happens next. But the
rules that make a process auditable are **declarative** — "a refund above €50
requires a coverage check", "an out-of-warranty claim may not be approved". Those
are not steps. They are constraints that hold (or are violated) *at* a state.

Sileno's move is to stop projecting one onto the other. An LPPN keeps both and
composes them: a procedural net for the causal mechanism, plus two declarative
nets — one over places (**lp-nodes**, §2.1, logical dependencies between
conditions) and one over transitions (**lt-nodes**, instantaneous propagation of
firing). Def. 3 makes the split explicit: with no declarative nodes an LPPN *is*
an ordinary Petri net; with no transitions it *is* an ASP program.

That gives the thing this repository needs. The norms become first-class
objects rather than sentences buried in a prompt, so exactly one artefact can be
(a) rendered into the instruction the agent is given, (b) evaluated against
every state the process passes through, and (c) used by the auditor. One source
of truth, three uses — which is what "auditable" has to mean in practice.

**Scope.** This is the hybrid operational semantics of §4.1, and only the
propositional fragment. The paper's declarative components are evaluated by an
ASP solver under stable-model semantics; here they are evaluated by stratified
forward chaining, which coincides with the stable model on the stratified
programs used in this repo but is *not* a general ASP solver — disjunction and
unstratified negation are rejected rather than solved. The paper's denotational
semantics (§4.2, Event Calculus → ASP) is not implemented; see docs/LPPN.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

# ---------------------------------------------------------------- literals
#
# Def. 1 (Literal and Extended literals). Given atoms A, the literals
# L = L⁺ ∪ L⁻ consist of positive literals L⁺ = A and negative (strongly
# negated) literals L⁻ = {-a | a ∈ A}. Extended literals L* = L ∪ L^not add
# default negation.
#
# Strong negation `-a` reifies "explicitly false" ("it does not rain"); default
# negation `not a` reifies "not derivable" ("it is unknown whether it rains").
# The distinction earns its keep in a claims process: "coverage was checked and
# refused" is not the same fact as "coverage was never checked".


@dataclass(frozen=True)
class Literal:
    atom: str
    strong_neg: bool = False   # '-a'  — explicitly false
    default_neg: bool = False  # 'not a' — not derivable

    @property
    def key(self) -> str:
        """The name this literal occupies in a derived set."""
        return f"-{self.atom}" if self.strong_neg else self.atom

    def holds(self, derived: set[str]) -> bool:
        present = self.key in derived
        return not present if self.default_neg else present

    def __str__(self) -> str:
        return ("not " if self.default_neg else "") + self.key


def lit(text: str) -> Literal:
    """Parse ``a`` / ``-a`` / ``not a`` / ``not -a``."""
    text = text.strip()
    default_neg = False
    if text.startswith("not "):
        default_neg, text = True, text[4:].strip()
    strong_neg = text.startswith("-")
    if strong_neg:
        text = text[1:].strip()
    if not text:
        raise ValueError("empty literal")
    return Literal(text, strong_neg, default_neg)


def lits(items: Iterable[str]) -> tuple[Literal, ...]:
    return tuple(lit(x) for x in items)


# ------------------------------------------------------------- lp/lt nodes

@dataclass(frozen=True)
class LPNode:
    """A logic-operator node over *places* (Def. 3, ``LP`` / ``C_LP``).

    Written as an ASP/Prolog rule ``head :- body``. This is the mechanism that
    turns the "source" marking M into the "ground" marking M* in step 1 of the
    execution cycle (§4.1): what is *implied* by the tokens actually present.
    """

    head: Literal
    body: tuple[Literal, ...] = ()
    note: str = ""

    def fires(self, derived: set[str]) -> bool:
        return all(b.holds(derived) for b in self.body)

    def __str__(self) -> str:
        if not self.body:
            return f"{self.head}."
        return f"{self.head} :- {', '.join(str(b) for b in self.body)}."


@dataclass(frozen=True)
class LTNode:
    """A logic-operator node over *transitions* (Def. 3, ``LT`` / ``C_LT``).

    An lt-node is a channel: when ``source`` fires, ``target`` fires
    *instantaneously* in the same step — step 3 of the execution cycle, where
    the source transition-event is closed into the ground event-marking E*.
    ``guard`` carries the contextual conditions that ``DE⁻_LT`` allows to come
    from places as well as transitions (paper, footnote 6).
    """

    source: str
    target: str
    guard: tuple[Literal, ...] = ()
    note: str = ""

    def __str__(self) -> str:
        g = f" [{', '.join(str(x) for x in self.guard)}]" if self.guard else ""
        return f"{self.source} ⟹ {self.target}{g}"


@dataclass(frozen=True)
class Norm:
    """An integrity constraint ``:- body`` — a state the process must not reach.

    Not a construct the paper names separately: in ASP an integrity constraint
    is just a rule with an empty head, and the paper's declarative components
    are ASP programs. Given a name and a message, it becomes the auditable unit
    this repository is built around.
    """

    id: str
    body: tuple[Literal, ...]
    message: str
    kind: str = "prohibition"  # or "obligation"
    #: prose rendered into the agent's instructions — the same norm, in words
    guidance: str = ""
    #: Dutch renderings of `guidance` and `message`, for the UI. They live on
    #: the norm rather than in a translation table in the frontend so that the
    #: constraint, the words the agent reads and the words a citizen reads all
    #: stay in one object — a reviewer checks all three in one glance. The
    #: engine, the CLI and the prompts keep using the English fields.
    guidance_nl: str = ""
    message_nl: str = ""

    def violated(self, derived: set[str]) -> bool:
        return all(b.holds(derived) for b in self.body)

    def __str__(self) -> str:
        return f":- {', '.join(str(b) for b in self.body)}.   % {self.id}"


# ------------------------------------------------------------------ layer

class StratificationError(ValueError):
    """Raised when the rule set is not stratified.

    Forward chaining is only equivalent to the stable model on stratified
    programs. Rather than silently return one arbitrary fixpoint for a program
    with recursion through negation, refuse it — an auditing layer that
    quietly picks an answer is worse than one that stops.
    """


@dataclass
class DeclarativeLayer:
    """The two declarative nets plus the norms, evaluated together."""

    lp_nodes: tuple[LPNode, ...] = ()
    lt_nodes: tuple[LTNode, ...] = ()
    norms: tuple[Norm, ...] = ()
    _strata: list[list[LPNode]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._strata = self._stratify()

    # -- stratification ------------------------------------------------------

    def _stratify(self) -> list[list[LPNode]]:
        """Assign each rule to a stratum so that a rule is evaluated only after
        every literal it negates is fully decided."""
        heads = {n.head.key for n in self.lp_nodes}
        level: dict[str, int] = {h: 0 for h in heads}

        # Longest-path relaxation: a negative dependency must strictly increase
        # the level, a positive one must not decrease it.
        for _ in range(len(heads) + 1):
            changed = False
            for node in self.lp_nodes:
                for b in node.body:
                    if b.key not in heads:
                        continue  # an input fact, already decided
                    want = level[b.key] + (1 if b.default_neg else 0)
                    if want > level[node.head.key]:
                        level[node.head.key], changed = want, True
            if not changed:
                break
        else:
            cyclic = sorted(h for h in heads if level[h] > len(heads))
            raise StratificationError(
                f"rules are not stratified (recursion through negation): {cyclic}"
            )

        top = max(level.values(), default=0)
        strata: list[list[LPNode]] = [[] for _ in range(top + 1)]
        for node in self.lp_nodes:
            strata[level[node.head.key]].append(node)
        return strata

    # -- step 1 of the execution cycle ---------------------------------------

    def ground(self, atoms: Iterable[str]) -> set[str]:
        """Source marking M (+ facts) → **ground marking M\\*** (§4.1 step 1).

        Everything entailed by what is actually the case. The transitions are
        then tested for enablement against M*, not against M (Def. 4) — so a
        purely declarative dependency can enable a transition without any token
        ever moving.
        """
        derived = set(atoms)
        for stratum in self._strata:
            while True:
                added = {n.head.key for n in stratum if n.fires(derived)} - derived
                if not added:
                    break
                derived |= added
        return derived

    # -- step 3 of the execution cycle ---------------------------------------

    def propagate(self, fired: Iterable[str], derived: set[str]) -> set[str]:
        """Source transition-event(s) → **ground event-marking E\\*** (§4.1 step 3).

        Closes the pre-fired set under the lt-nodes: firing one transition may
        instantaneously fire others. Guards are checked against the ground
        marking.
        """
        events = set(fired)
        while True:
            added = {
                n.target
                for n in self.lt_nodes
                if n.source in events
                and n.target not in events
                and all(g.holds(derived) for g in n.guard)
            }
            if not added:
                return events
            events |= added

    # -- auditing ------------------------------------------------------------

    def violations(self, derived: set[str]) -> list[Norm]:
        return [n for n in self.norms if n.violated(derived)]

    def inconsistencies(self, derived: set[str]) -> list[str]:
        """Atoms asserted both true and explicitly false (Def. 1).

        In a claims process this is a live failure mode, not a curiosity: it is
        what "the coverage agent said covered and the assessor recorded not
        covered" looks like once both are reified.
        """
        return sorted(a for a in derived if not a.startswith("-") and f"-{a}" in derived)

    def guidance(self) -> str:
        """Render the norms as the instruction text an agent is given.

        The point of the whole module: the sentence the model reads and the
        constraint the auditor evaluates are generated from one object, so they
        cannot drift apart.
        """
        lines = []
        for n in self.norms:
            if n.guidance:
                lines.append(f"- ({n.id}) {n.guidance}")
        return "\n".join(lines)


# ------------------------------------------------------------------- LPPN

@dataclass
class LPPN:
    """A procedural net (Def. 2) plus its declarative nets (Def. 3).

    ``step`` implements the four-step hybrid operational cycle of §4.1
    literally, which is the whole reason to keep this class rather than folding
    the logic into the scheduler: the code should be readable next to the paper.
    """

    net: object            # petrinet.core.PetriNet — kept loose to avoid a cycle
    declarative: DeclarativeLayer
    #: extra atoms describing the case, outside the marking (facts about objects)
    context: tuple[str, ...] = ()

    def marking_atoms(self, marking: Mapping[str, int]) -> set[str]:
        return {f"place:{p}" for p, n in marking.items() if n}

    def ground_marking(self, marking: Mapping[str, int],
                       context: Iterable[str] = ()) -> set[str]:
        """Step 1: M → M*."""
        return self.declarative.ground(
            self.marking_atoms(marking) | set(self.context) | set(context)
        )

    def enabled(self, marking: Mapping[str, int], context: Iterable[str] = ()) -> list:
        """Def. 4: enabled *in the ground marking* M*, not in M."""
        ground = self.ground_marking(marking, context)
        return [
            t
            for t in self.net.transitions  # type: ignore[attr-defined]
            if all(f"place:{a.place}" in ground for a in t.inputs)
        ]

    def step(self, marking: Mapping[str, int], prefire: Sequence[str],
             context: Iterable[str] = ()) -> tuple[dict, set[str], list[Norm]]:
        """Run one full cycle and return ``(marking', fired, violations)``.

        1. ground the marking          → M*
        2. ``prefire`` is the selection (Def. 5) — made by the caller, because
           in this repository that choice is the business decision an agent makes
        3. close it under the lt-nodes → E*
        4. fire every event in E*
        """
        ground = self.ground_marking(marking, context)
        events = self.declarative.propagate(prefire, ground)

        out = dict(marking)
        for tid in events:
            t = self.net.transition(tid)  # type: ignore[attr-defined]
            for arc in t.inputs:
                out[arc.place] = out.get(arc.place, 0) - arc.weight
                if out[arc.place] <= 0:
                    out.pop(arc.place, None)
        for tid in events:
            t = self.net.transition(tid)  # type: ignore[attr-defined]
            for arc in t.outputs:
                out[arc.place] = out.get(arc.place, 0) + arc.weight

        after = self.declarative.ground(
            self.marking_atoms(out)
            | set(self.context)
            | set(context)
            | {f"fired:{e}" for e in events}
        )
        return out, events, self.declarative.violations(after)
