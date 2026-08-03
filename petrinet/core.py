"""A small, dependency-free Petri net engine.

A Petri net is a bipartite graph of *places* (conditions / state, drawn as
circles) and *transitions* (events / work, drawn as bars). Places hold
*tokens*; the distribution of tokens over places is the *marking* — the
complete state of the process.

A transition is *enabled* when every input place holds at least as many
tokens as the connecting arc's weight. Firing it consumes the input tokens
and produces tokens on the output places.

Why this matters for business processes: unlike a flowchart, a Petri net can
express concurrency (one transition producing into two places = AND-split),
synchronisation (one transition consuming from two places = AND-join, it
simply cannot fire until both branches have arrived), conflict (two
transitions competing for the same token = an exclusive choice), and loops —
all with formal semantics you can *verify* rather than eyeball.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

Marking = dict[str, int]


@dataclass(frozen=True)
class Place:
    id: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class Arc:
    place: str
    weight: int = 1


@dataclass(frozen=True)
class Transition:
    id: str
    label: str
    inputs: tuple[Arc, ...]
    outputs: tuple[Arc, ...]
    #: free-form annotations — the AS-IS model stores the human role and
    #: handling time here, the TO-BE model stores the agent and its autonomy
    #: level. The engine never reads these; the compiler and the report do.
    meta: dict = field(default_factory=dict, compare=False)

    @property
    def input_places(self) -> tuple[str, ...]:
        return tuple(a.place for a in self.inputs)

    @property
    def output_places(self) -> tuple[str, ...]:
        return tuple(a.place for a in self.outputs)


class PetriNetError(ValueError):
    pass


@dataclass
class PetriNet:
    name: str
    places: tuple[Place, ...]
    transitions: tuple[Transition, ...]
    initial_marking: Marking
    #: the place that means "case finished" — used by the soundness check
    final_place: str | None = None

    def __post_init__(self) -> None:
        self._places = {p.id: p for p in self.places}
        self._transitions = {t.id: t for t in self.transitions}
        self.validate()

    # ---------------------------------------------------------------- lookup

    def place(self, pid: str) -> Place:
        return self._places[pid]

    def transition(self, tid: str) -> Transition:
        return self._transitions[tid]

    def validate(self) -> None:
        if len(self._places) != len(self.places):
            raise PetriNetError("duplicate place id")
        if len(self._transitions) != len(self.transitions):
            raise PetriNetError("duplicate transition id")
        for t in self.transitions:
            for arc in t.inputs + t.outputs:
                if arc.place not in self._places:
                    raise PetriNetError(f"transition {t.id!r} references unknown place {arc.place!r}")
                if arc.weight < 1:
                    raise PetriNetError(f"transition {t.id!r} has arc weight < 1")
            if not t.inputs:
                raise PetriNetError(f"transition {t.id!r} has no input place (would fire forever)")
        for pid in self.initial_marking:
            if pid not in self._places:
                raise PetriNetError(f"initial marking references unknown place {pid!r}")
        if self.final_place and self.final_place not in self._places:
            raise PetriNetError(f"unknown final place {self.final_place!r}")

    # ------------------------------------------------------------- semantics

    def is_enabled(self, marking: Mapping[str, int], t: Transition) -> bool:
        return all(marking.get(a.place, 0) >= a.weight for a in t.inputs)

    def enabled(self, marking: Mapping[str, int]) -> list[Transition]:
        return [t for t in self.transitions if self.is_enabled(marking, t)]

    def consume(self, marking: Marking, t: Transition) -> Marking:
        """Remove the input tokens of ``t``. Returns a new marking."""
        if not self.is_enabled(marking, t):
            raise PetriNetError(f"transition {t.id!r} is not enabled in marking {dict(marking)}")
        out = dict(marking)
        for a in t.inputs:
            out[a.place] = out.get(a.place, 0) - a.weight
            if out[a.place] == 0:
                del out[a.place]
        return out

    def produce(self, marking: Marking, t: Transition) -> Marking:
        """Add the output tokens of ``t``. Returns a new marking."""
        out = dict(marking)
        for a in t.outputs:
            out[a.place] = out.get(a.place, 0) + a.weight
        return out

    def fire(self, marking: Marking, t: Transition) -> Marking:
        """Atomically consume then produce — the classic firing rule."""
        return self.produce(self.consume(marking, t), t)

    # ------------------------------------------------------------ step rules

    def maximal_step(
        self,
        marking: Mapping[str, int],
        resolve_conflict: Callable[[list[Transition], Mapping[str, int]], Transition] | None = None,
    ) -> list[Transition]:
        """Pick a maximal set of transitions that can fire *simultaneously*.

        Two enabled transitions can fire in the same step only if there are
        enough tokens for both. Where they compete for the same token they are
        in *conflict* and exactly one may go — that is a business decision, so
        ``resolve_conflict`` gets to make it (in the agentic build, an LLM).
        """
        budget = dict(marking)
        chosen: list[Transition] = []
        pending = deque(self.enabled(marking))
        #: One conflict is one business decision, so resolve each competing set
        #: at most once per step — re-queueing the loser must not re-ask.
        decided: dict[frozenset[str], str] = {}

        while pending:
            t = pending.popleft()
            if not self.is_enabled(budget, t):
                continue  # its token was taken by an earlier pick
            rivals = [
                other
                for other in pending
                if self.is_enabled(budget, other) and set(other.input_places) & set(t.input_places)
            ]
            if rivals and resolve_conflict is not None:
                group = [t, *rivals]
                key = frozenset(x.id for x in group)
                if key not in decided:
                    decided[key] = resolve_conflict(group, budget).id
                winner = next(x for x in group if x.id == decided[key])
                if winner.id != t.id:
                    # put t back behind the winner and re-run the loop
                    pending.remove(winner)
                    pending.appendleft(t)
                    pending.appendleft(winner)
                    continue
            chosen.append(t)
            for a in t.inputs:
                budget[a.place] = budget.get(a.place, 0) - a.weight
        return chosen

    # ------------------------------------------------------------- soundness

    def reachable(self, limit: int = 20_000) -> tuple[set[tuple[tuple[str, int], ...]], bool]:
        """Bounded breadth-first exploration of the reachability graph.

        Returns the set of reachable markings and whether exploration was
        complete (``False`` means the net is unbounded or too large and the
        soundness verdict below is only a partial result).
        """
        start = _key(self.initial_marking)
        seen = {start}
        queue = deque([dict(self.initial_marking)])
        complete = True
        while queue:
            if len(seen) > limit:
                complete = False
                break
            m = queue.popleft()
            for t in self.enabled(m):
                nxt = self.fire(m, t)
                k = _key(nxt)
                if k not in seen:
                    seen.add(k)
                    queue.append(nxt)
        return seen, complete

    def check_soundness(self) -> "SoundnessReport":
        """A workflow-net soundness check.

        Three classic properties:
        1. *Option to complete* — the final marking is reachable.
        2. *Proper completion / no deadlock* — every marking with no enabled
           transition is the final marking (nothing gets permanently stuck).
        3. *No dead transitions* — every transition is enabled somewhere, i.e.
           no step of the documented process is unreachable in practice.
        """
        markings, complete = self.reachable()
        final_key = _key({self.final_place: 1}) if self.final_place else None

        deadlocks: list[Marking] = []
        fired: set[str] = set()
        reaches_final = final_key is None
        for k in markings:
            m = dict(k)
            if final_key is not None and k == final_key:
                reaches_final = True
            en = self.enabled(m)
            fired.update(t.id for t in en)
            if not en and k != final_key:
                deadlocks.append(m)

        dead = [t.id for t in self.transitions if t.id not in fired]
        return SoundnessReport(
            net=self.name,
            markings_explored=len(markings),
            exploration_complete=complete,
            can_complete=reaches_final,
            deadlocks=deadlocks,
            dead_transitions=dead,
        )

    # --------------------------------------------------------------- replay

    def is_legal_firing_sequence(self, sequence: Iterable[str]) -> tuple[bool, str]:
        """Replay a recorded run against the model.

        This is the formal-verification backstop for the audit: whatever the
        agents *claim* they did, the sequence they actually fired either
        replays against the net or it does not.
        """
        m = dict(self.initial_marking)
        for i, tid in enumerate(sequence):
            if tid not in self._transitions:
                return False, f"step {i}: unknown transition {tid!r}"
            t = self._transitions[tid]
            if not self.is_enabled(m, t):
                return False, f"step {i}: {tid!r} fired while not enabled (marking {m})"
            m = self.fire(m, t)
        return True, "sequence replays cleanly against the model"


@dataclass
class SoundnessReport:
    net: str
    markings_explored: int
    exploration_complete: bool
    can_complete: bool
    deadlocks: list[Marking]
    dead_transitions: list[str]

    @property
    def sound(self) -> bool:
        return self.can_complete and not self.deadlocks and not self.dead_transitions

    def render(self) -> str:
        lines = [f"soundness: {self.net}"]
        ok = "PASS" if self.sound else "FAIL"
        lines.append(f"  verdict            : {ok}")
        lines.append(f"  markings explored  : {self.markings_explored}"
                     f"{'' if self.exploration_complete else ' (truncated — net may be unbounded)'}")
        lines.append(f"  option to complete : {'yes' if self.can_complete else 'NO'}")
        lines.append(f"  deadlocks          : {len(self.deadlocks) or 'none'}")
        for d in self.deadlocks[:3]:
            lines.append(f"      stuck at {d}")
        lines.append(f"  dead transitions   : {', '.join(self.dead_transitions) or 'none'}")
        return "\n".join(lines)


def _key(marking: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((p, n) for p, n in marking.items() if n))


def render_marking(net: PetriNet, marking: Mapping[str, int]) -> str:
    live = [f"{net.place(p).label}×{n}" if n > 1 else net.place(p).label
            for p, n in sorted(marking.items()) if n]
    return " + ".join(live) if live else "(empty)"
