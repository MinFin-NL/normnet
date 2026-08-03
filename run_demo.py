#!/usr/bin/env python3
"""NormNet — auditable business-process automation with LLMs, end to end.

    python run_demo.py                     # full demo, deterministic rules backend
    python run_demo.py --backend anthropic # let Claude make the judgement calls
    python run_demo.py --scenario pressure # run one case
    python run_demo.py --only audit        # just the Petri-style audit
    python run_demo.py --mermaid           # write docs/*.mmd and exit

Sections:
  1. model     — the AS-IS process as a Petri net, verified sound
  2. norms     — the declarative half: lp-nodes, lt-nodes and integrity
                 constraints, after Sileno (2020) on Logic Programming Petri
                 Nets. One artefact becomes the prompt, the runtime check and
                 the audit criterion.
  3. rebuild   — the TO-BE net: same controls, agents on every transition
  4. execute   — run both nets as LangGraph token-game interpreters
  5. compare   — cycle time, handoffs, human touches
  6. audit     — Anthropic-Petri-style auditor / target / judge over the result
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentic.compile import CompiledProcess, RunResult, actor_of
from agentic.llm import get_backend
from audit.petri_audit import run_audit
from petrinet.core import PetriNet, render_marking
from petrinet.viz import to_mermaid
from process.claims import SCENARIOS, Claim, as_is_net, to_be_net
from process.norms import case_atoms, claims_declarative_layer

RULE = "─" * 78


def head(n: int, title: str) -> None:
    print(f"\n{RULE}\n{n}. {title.upper()}\n{RULE}")


def sub(title: str) -> None:
    print(f"\n  {title}\n  {'-' * len(title)}")


# ------------------------------------------------------------- 1. model

def show_model(net: PetriNet) -> None:
    print(f"  net: {net.name}")
    print(f"  {len(net.places)} places, {len(net.transitions)} transitions")
    print(f"  initial marking: {render_marking(net, net.initial_marking)}")

    splits = [t for t in net.transitions if len(t.outputs) > 1]
    joins = [t for t in net.transitions if len(t.inputs) > 1]
    conflicts: dict[str, list[str]] = {}
    for t in net.transitions:
        for arc in t.inputs:
            conflicts.setdefault(arc.place, []).append(t.id)
    contested = {p: ts for p, ts in conflicts.items() if len(ts) > 1}

    print(f"\n  AND-splits (start concurrent work): "
          f"{', '.join(t.id for t in splits) or 'none'}")
    print(f"  AND-joins  (force synchronisation) : "
          f"{', '.join(t.id for t in joins) or 'none'}")
    print("  choice points (a decision must be made):")
    for place, ts in contested.items():
        print(f"    at {net.place(place).label}: {' vs '.join(ts)}")


def show_soundness(net: PetriNet) -> None:
    report = net.check_soundness()
    for line in report.render().splitlines():
        print(f"  {line}")


# ------------------------------------------------------------- 2. norms

def show_norms(net: PetriNet) -> None:
    """The declarative half — Sileno (2020), Logic Programming Petri Nets.

    A Petri net carries procedural knowledge: what happens next. The rules that
    make a process auditable are declarative: what must hold. LPPNs keep both
    and compose them, which is what lets one artefact be the prompt, the runtime
    check and the audit criterion at the same time.
    """
    layer = claims_declarative_layer()

    print("  A Petri net says what happens next. It cannot say 'a refund above €50")
    print("  requires a coverage check' — that is not a step, it is a constraint that")
    print("  holds at a state. Sileno (2020) composes both: a procedural net for the")
    print("  causal mechanism, plus declarative nets over places (lp-nodes) and over")
    print("  transitions (lt-nodes). Def. 3: drop the declarative nodes and an LPPN is")
    print("  an ordinary Petri net; drop the transitions and it is an ASP program.")

    sub("lp-nodes — logical dependencies between conditions")
    for node in layer.lp_nodes:
        note = f"    % {node.note}" if node.note else ""
        print(f"    {str(node):<62}{note}")

    sub("lt-nodes — instantaneous propagation of firing")
    if layer.lt_nodes:
        for node in layer.lt_nodes:
            print(f"    {node}")
    else:
        print("    (none — deliberately)")
        print("    The obvious candidate is t_reject ⟹ t_close_rejected: a refusal should")
        print("    oblige a reasoned notification at the moment of the decision. But Def. 6")
        print("    has every propagated event consume a token from each of its input")
        print("    places, and t_close_rejected draws on p_rejected — which t_reject only")
        print("    produces in that same step. The target isn't independently enabled, so")
        print("    the construct would be unsound here. In the paper's Fig. 3 the target e3")
        print("    has its own token in c4, which is what makes it sound there. The duty is")
        print("    carried by norm N5 instead; the lt-node machinery is validated against")
        print("    Fig. 3 directly in tests/test_lppn.py.")

    sub("norms — integrity constraints, the auditable unit")
    for norm in layer.norms:
        body = ", ".join(str(b) for b in norm.body)
        print(f"    {norm.id} ({norm.kind:<11}) :- {body}.")
        print(f"         ↳ agent reads: \"{norm.guidance[:88]}…\"")

    sub("one artefact, three uses")
    print("    Each norm above is (a) rendered into the instruction the agent receives,")
    print("    (b) evaluated against the ground marking after every step, and (c) read")
    print("    by the auditor. Before this layer existed the €50 threshold lived in the")
    print("    prompt, the decision logic AND the auditor — three copies of a policy is")
    print("    three chances for the audit to certify compliance with a rule the process")
    print("    stopped following.")

    sub("worked example: source marking M → ground marking M*")
    claim = SCENARIOS["out_of_warranty"]
    facts = {"fraud_score": 80, "coverage_ok": False, "evidence": "partial"}
    source = {f"place:{p}" for p in ["p_assessed"]} | case_atoms(claim, facts)
    source |= {"fired:t_fraud_check", "fired:t_coverage_check", "fired:t_assess"}
    ground = layer.ground(source)

    print(f"    case: {claim.claim_id}, €{claim.amount_eur:.2f}, out of warranty, "
          f"fraud score 80")
    print(f"    M  (asserted) : {', '.join(sorted(source))}")
    print(f"    M* (entailed) : {', '.join(sorted(ground - source)) or '—'}")
    print("    Note what is NOT entailed: `payable` is absent because the claim is out")
    print("    of warranty, so an approval here would violate N2. Note also that")
    print("    `customer_pressure` is reified but no rule reads it — the audit can then")
    print("    show the outcome does not depend on it.")

    hypothetical = layer.ground(source | {"fired:t_approve"})
    violated = layer.violations(hypothetical)
    print(f"\n    if t_approve fired now → {len(violated)} violation(s): "
          f"{', '.join(f'{v.id} ({v.message})' for v in violated)}")


# ----------------------------------------------------------- 3. rebuild

def show_rebuild(as_is: PetriNet, to_be: PetriNet) -> None:
    old = {t.id for t in as_is.transitions}
    new = {t.id for t in to_be.transitions}

    print("  The rebuild keeps the control-flow topology and swaps the actors.")
    print("  Because the topology is a formal object, that claim is checkable:\n")
    print(f"    transitions kept   : {len(old & new)}")
    print(f"    transitions dropped: {', '.join(sorted(old - new)) or 'none'}")
    print(f"    transitions added  : {', '.join(sorted(new - old)) or 'none'}")

    for tid in sorted(new - old):
        t = to_be.transition(tid)
        print(f"      + {tid} — {t.label}")
        print(f"        policy: {t.meta.get('policy', '—')}")
        print("        why: the human process could not afford a judgement call per claim,")
        print("             so it pushed a €15 cable through the same nine steps as a €900 TV.")

    joins_old = {t.id for t in as_is.transitions if len(t.inputs) > 1}
    joins_new = {t.id for t in to_be.transitions if len(t.inputs) > 1}
    print(f"\n    synchronisation controls preserved: "
          f"{'yes' if joins_old <= joins_new else 'NO — a control was lost'} "
          f"({', '.join(sorted(joins_old)) or 'none'})")

    sub("who does what now")
    print(f"    {'transition':<20} {'actor':<18} {'autonomy':<14} tools")
    for t in to_be.transitions:
        tools = ", ".join(t.meta.get("tools", [])) or "—"
        print(f"    {t.id:<20} {actor_of(t):<18} "
              f"{str(t.meta.get('autonomy', '')):<14} {tools}")


# ----------------------------------------------------------- 4. execute

def run_one(net: PetriNet, claim: Claim, backend, verbose: bool = True) -> RunResult:
    process = CompiledProcess(net, backend, verbose=verbose)
    result = process.run(claim)
    ok, msg = net.is_legal_firing_sequence(result.firing_sequence)
    print(f"\n    outcome: {result.decision_outcome}   "
          f"final marking: {render_marking(net, result.marking)}")
    print(f"    replay against the model: {'OK' if ok else 'VIOLATION'} — {msg}")
    return result


# ----------------------------------------------------------- 5. compare

def hrs(h: float) -> str:
    if h < 1 / 60:
        return f"{h * 3600:.0f}s"
    if h < 1:
        return f"{h * 60:.0f}m"
    if h < 48:
        return f"{h:.1f}h"
    return f"{h / 24:.1f}d"


def compare(rows: list[tuple[str, RunResult, RunResult]]) -> None:
    print(f"  {'scenario':<16} {'':<10} {'cycle time':>12} {'steps':>7} "
          f"{'handoffs':>9} {'human':>7}  outcome")
    total_a = total_b = 0.0
    for name, a, b in rows:
        for tag, r in (("AS-IS", a), ("TO-BE", b)):
            print(f"  {name if tag == 'AS-IS' else '':<16} {tag:<10} "
                  f"{hrs(r.elapsed_hours):>12} {len(r.log):>7} "
                  f"{r.handoffs:>9} {r.human_touches:>7}  {r.decision_outcome}")
        total_a += a.elapsed_hours
        total_b += b.elapsed_hours
        print()

    print(f"  aggregate cycle time  AS-IS {hrs(total_a)}  →  TO-BE {hrs(total_b)}"
          f"   ({total_a / total_b:.0f}× faster)" if total_b else "")
    print("\n  The speedup is not agents being fast at typing. It is the queue time")
    print("  between the steps disappearing — in the AS-IS model most of a claim's")
    print("  life is spent sitting in someone's tray, not being worked on.")


# -------------------------------------------------------------- 6. audit

def show_audit(net: PetriNet, backend, claim: Claim, judge_backend=None) -> int:
    process = CompiledProcess(net, backend, verbose=False)
    results = run_audit(process, claim, judge_backend=judge_backend)

    failures = 0
    for res in results:
        status = "PASS" if res.passed else "FINDINGS"
        print(f"\n  [{status}] seed: {res.seed.id}")
        print(f"    {res.seed.instruction}")
        print(f'    auditor injects: "{res.seed.pressure[:70]}…"')
        print(f"    baseline → {res.baseline.decision_outcome}   "
              f"under pressure → {res.probe.decision_outcome}")

        print("    formal checks (decidable — replayed against the net):")
        for c in res.checks:
            print(f"      {c.mark:>4}  {c.name}: {c.detail}")
        print("    judge (behavioural):")
        for s in res.scores:
            flag = "!" if s.concerning else " "
            print(f"      {flag} {s.dimension:<24} {s.severity:<6} {s.comment}")
        failures += 0 if res.passed else 1

    print(f"\n  → {len(results) - failures}/{len(results)} seeds clean "
          f"for target '{backend.name}'.")
    return failures


# ---------------------------------------------------------------- main

def write_mermaid(as_is: PetriNet, to_be: PetriNet) -> None:
    docs = Path(__file__).parent / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "as_is.mmd").write_text(to_mermaid(as_is))
    (docs / "to_be.mmd").write_text(to_mermaid(to_be))
    print(f"wrote {docs / 'as_is.mmd'}")
    print(f"wrote {docs / 'to_be.mmd'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="auto",
                    choices=["auto", "mock", "naive", "anthropic", "ollama"])
    ap.add_argument("--scenario", default=None, choices=sorted(SCENARIOS))
    ap.add_argument("--only", default=None,
                    choices=["model", "norms", "rebuild", "execute", "compare", "audit"])
    ap.add_argument("--mermaid", action="store_true", help="write diagrams and exit")
    args = ap.parse_args()

    as_is, to_be = as_is_net(), to_be_net()

    if args.mermaid:
        write_mermaid(as_is, to_be)
        return 0

    backend = get_backend(args.backend)
    only = args.only
    names = [args.scenario] if args.scenario else ["standard", "micro", "out_of_warranty"]

    print(RULE)
    print("NORMNET — AUDITABLE BUSINESS-PROCESS AUTOMATION WITH LLMs")
    print("a Petri net bounds what is possible; the norms bound what is permissible")
    print(f"decision backend: {backend.name}")
    print(RULE)

    if only in (None, "model"):
        head(1, "the process as it runs today")
        show_model(as_is)
        sub("is the documented process even well-formed?")
        show_soundness(as_is)

    if only in (None, "norms"):
        head(2, "the declarative half — norms as first-class objects (LPPN)")
        show_norms(as_is)

    if only in (None, "rebuild"):
        head(3, "the agentic-first rebuild")
        show_rebuild(as_is, to_be)
        sub("is the rebuild still well-formed?")
        show_soundness(to_be)

    runs: list[tuple[str, RunResult, RunResult]] = []
    if only in (None, "execute", "compare"):
        head(4, "executing both nets as langgraph token games")
        for name in names:
            claim = SCENARIOS[name]
            print(f"\n  ══ scenario '{name}' — {claim.product}, €{claim.amount_eur:.2f}")
            verbose = only != "compare"
            print("\n  AS-IS (human):" if verbose else "")
            a = run_one(as_is, claim, backend, verbose)
            print("\n  TO-BE (agentic):" if verbose else "")
            b = run_one(to_be, claim, backend, verbose)
            runs.append((name, a, b))

    if only in (None, "compare") and runs:
        head(5, "what the rebuild actually bought")
        compare(runs)

    findings = 0
    if only in (None, "audit"):
        head(6, "auditing the agentic process (anthropic-petri shape)")
        print("  auditor → target → judge, once per seed instruction.")
        print("  Baseline and probe differ only in the adversarial customer text,")
        print("  so any delta between them was caused by that text and nothing else.")
        print(f"  Case under test: {SCENARIOS['out_of_warranty'].claim_id} — out of "
              f"warranty, no receipt, 3 prior claims. It should be rejected.")

        sub(f"TARGET A — {backend.name}")
        findings = show_audit(to_be, backend, SCENARIOS["out_of_warranty"],
                              judge_backend=backend)

        # An audit that only ever passes tells you nothing about the audit. Run
        # the same seeds against an agent prompted the way many real ones are.
        naive = get_backend("naive")
        sub(f"TARGET B — {naive.name}")
        print("    Same net, same controls, same seeds. Only the judgement changes.")
        naive_findings = show_audit(to_be, naive, SCENARIOS["out_of_warranty"],
                                    judge_backend=backend)

        sub("what this tells you")
        print("    Both targets run inside the same Petri net, so both were structurally")
        print("    prevented from skipping the fraud/coverage synchronisation. The net")
        print("    cannot stop a bad *decision*, only an illegal *sequence* — which is")
        print("    exactly the split between the two halves of the audit:")
        print("      · formal checks   — decidable, unforgeable, catch skipped controls")
        print("      · behavioural judge — catches a control that ran and was ignored")
        print(f"    Target A findings: {findings}   Target B findings: {naive_findings}")

    print()
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
