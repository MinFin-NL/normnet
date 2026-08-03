# The declarative half: Logic Programming Petri Nets

## Reference

> Giovanni Sileno (2020). **Operationalizing Declarative and Procedural
> Knowledge: a Benchmark on Logic Programming Petri Nets (LPPNs).**
> In: *International Conference on Logic Programming 2020 Workshop Proceedings*,
> co-located with the 36th ICLP, Rende, Italy, 18–19 September 2020, Article 7.
> CEUR Workshop Proceedings, Vol. 2678. CEUR-WS.
> Informatics Institute, University of Amsterdam. Licence: CC BY 4.0.
> PDF: <https://pure.uva.nl/ws/files/63279071/paper7.pdf> ·
> arXiv: <https://arxiv.org/abs/1701.07657> ·
> Reference interpreter: <https://github.com/s1l3n0/pypneu>

Implemented here in [`petrinet/lppn.py`](../petrinet/lppn.py); applied to the
claims process in [`process/norms.py`](../process/norms.py); validated against
the paper's own running example in [`tests/test_lppn.py`](../tests/test_lppn.py).

---

## Why this paper, for this problem

The goal is to automate a business process with LLMs **auditably**. A Petri net
alone gets you a long way — concurrency, synchronisation, replayable traces —
but it carries only *procedural* knowledge: what happens next. It has no way to
express the things an auditor actually asks about:

- a refund above €50 requires a coverage check
- an out-of-warranty claim may not be approved
- a refusal must be communicated with a reason

None of those are steps. They are constraints that hold, or fail to hold, at a
state. Put them in a prompt and they are unverifiable prose. Put them in the
control flow and you get a net that encodes one policy version and has to be
redrawn when the policy changes.

Sileno's framing is that these are two genuinely different kinds of knowledge
and the usual mistake is projecting one onto the other. Modelling declarative
knowledge procedurally means "adding conditions that disable all transitions
that might produce that outcome"; modelling procedural knowledge declaratively
means snapshot-and-timestamp encodings (situation/event/fluent calculus). Both
work and both are awkward. An LPPN keeps both and composes them.

That is exactly the shape this repo needed. It gives the norms an existence
independent of both the prompt and the net, so **one artefact** can be:

1. rendered into the instruction the agent receives,
2. evaluated against every state the process passes through,
3. read by the auditor when it grades the run.

Before this layer, the €50 threshold existed in three places — the prompt
string, the decision logic, and a hand-written check in the auditor. Three
copies of a policy is three chances for the audit to certify compliance with a
rule the process is no longer following. That is the failure mode that makes
"we have an audit" worthless, and it is a *design* problem, not a diligence
problem.

---

## The constructs, and where they are in this repo

| Paper | Meaning | Here |
|---|---|---|
| **procedural net** (Def. 2) | `N = ⟨P,T,E⟩` — places, transitions, arcs | [`petrinet/core.py`](../petrinet/core.py) |
| **lp-node** (Def. 3, `LP`/`C_LP`) | logic operator over **places**: dependencies between conditions | `LPNode` — e.g. `auto_settle_eligible :- low_value, in_warranty, not repeat_claimant.` |
| **lt-node** (Def. 3, `LT`/`C_LT`) | logic operator over **transitions**: instantaneous propagation of firing | `LTNode` — implemented and tested; see the modelling note below |
| **integrity constraint** | ASP rule with an empty head, `:- body` | `Norm` — given an id, a `kind` and prose, it becomes the auditable unit |
| **literals** (Def. 1) | `L = L⁺ ∪ L⁻`, plus default negation `not` | `Literal` — `a`, `-a`, `not a`, `not -a` |
| **ground marking `M*`** (§4.1 step 1) | what the tokens actually present *entail* | `DeclarativeLayer.ground()` |
| **ground event-marking `E*`** (§4.1 step 3) | the pre-fired event closed under lt-nodes | `DeclarativeLayer.propagate()` |
| **enabledness** (Def. 4) | `∀p ∈ •t, M*(p)=1` — against `M*`, not `M` | `LPPN.enabled()` |

Def. 3 has a property worth stating plainly: with no declarative nodes an LPPN
*is* an ordinary Petri net, and with no transitions it *is* an ASP program. The
declarative layer here is genuinely optional in the same way — there is a test
for it.

### Strong vs. default negation

Def. 1 distinguishes `-a` ("explicitly false") from `not a` ("not derivable").
In a claims process this is not academic:

- `-in_warranty` — we checked, and the product is out of warranty.
- `not in_warranty` — we have not established that it is in warranty.

The first justifies a rejection. The second justifies asking. `case_atoms()`
asserts the strong form whenever a check has actually run, which is why the
auditor can tell "coverage refused" from "coverage never checked".

---

## The four-step execution cycle (§4.1)

The paper's hybrid operational semantics runs each step as:

1. the declarative net of **places** turns the source marking `M` into the
   ground marking `M*`;
2. an enabled transition is selected to **pre-fire** (Def. 5);
3. the declarative net of **transitions** closes that event into the ground
   event-marking `E*` (all instantaneous propagations);
4. every event in `E*` fires, consuming and producing tokens (Def. 6).

`LPPN.step()` implements this literally, in that order, so the code can be read
next to the paper. Step 2 is the interesting one for this repository: the
selection is *the business decision*, and it is where the LLM is called. The
procedural net decides what is possible; the model chooses among those options;
the declarative net says whether the result is permissible.

---

## Where this implementation diverges from the paper

Stated plainly, because an auditing layer that overstates its own guarantees is
worse than none.

| | Paper | Here |
|---|---|---|
| Declarative evaluation | ASP under stable-model semantics (`clingo`) | Stratified forward chaining. Coincides with the stable model on the stratified programs used here; **not** a general ASP solver. Disjunctive heads and recursion through negation are *rejected* (`StratificationError`), never silently resolved to an arbitrary fixpoint. |
| Firing policy | **Interleaving** — exactly one transition pre-fires per step (Def. 5) | **Maximal step** — every non-conflicting enabled transition fires concurrently. Deliberate: the point of modelling a business process is that the fraud and coverage checks genuinely run at the same time. `LPPN.step()` accepts any pre-fire set, so interleaving is available by passing a singleton. |
| Denotational semantics (§4.2) | Full mapping to ASP + Event Calculus (`holdsAt`/`firesAt`/`initiates`/`terminates`/`clipped`) | Not implemented. The hybrid operational semantics is the one this repo needs; the paper's benchmark finds it the more efficient of the two on sequences anyway. |
| Labelling | `C_P : P → L*`, `C_T : T → L` — places and transitions carry literals | Simplified to a naming convention: `place:<id>` and `fired:<id>`. Equivalent for the propositional fragment, and readable in a trace. |
| Marking | Boolean, condition/event nets | Integer-valued, though the claims net stays 1-bounded in practice. |

---

## A modelling note: why there are no lt-nodes in the claims process

`LT_NODES` in `process/norms.py` is empty, and the reason is a real semantic
constraint rather than an omission.

The obvious candidate is `t_reject ⟹ t_close_rejected`. A refusal ought to
oblige a reasoned notification *at the moment of the decision*, and expressing
that as instantaneous propagation would make "refused but never told the
customer" an inexpressible trace — much stronger than checking for it after the
fact.

It is the wrong construct here all the same. Def. 6 has every event in `E*`
consume a token from each of its input places. `t_close_rejected` draws on
`p_rejected`, which `t_reject` only *produces* in the very same step, so the
propagation target is not independently enabled and firing it would violate the
firing rule. In the paper's Fig. 3 the target `e3` has its own token in `c4` —
that independence is precisely what makes the construct sound there.

So the notification duty is carried by norm **N5**, an obligation evaluated
against the ground marking. The lt-node machinery is implemented and validated
against Fig. 3 directly.

### Prohibitions and obligations are not checked at the same moment

Conflating them produces false positives, and this repo produced one before it
was fixed:

- A **prohibition** (`N1`: must not auto-settle an ineligible claim) is violated
  the instant its state is reached, and can never be undone. Checked every round.
- An **obligation** (`N5`: a refusal must be communicated) is violated only if
  the process *terminates* without discharging it. Between `t_reject` and
  `t_close_rejected` it is merely **pending**, which is a normal state to be in.
  Checked at the terminal state only.

Check obligations eagerly and every rejection looks non-compliant for a few
rounds, which trains everyone to ignore the audit.

---

## Fidelity test: the paper's Fig. 3

`tests/test_lppn.py` encodes the LPPN of Fig. 3 (places `c1`–`c5`, transitions
`e1`, `e2`, `e3`, an lt-node `e1 ⟹ e3`, and an lp-node making `c2` sufficient
for `c5`) and asserts the execution paths §2 enumerates:

1. `e2` fires, consuming `c1`; `e3` fires, consuming `c4` and producing `c3`.
2–3. `e3` fires, and then one of `e1` or `e2`.
4. `e1` fires, consuming `c1`; the firing **propagates** to `e3`; `e1` also
   produces `c2`; the existence of `c2` immediately reifies `c5`.

Path 4 is the load-bearing one: it exercises lt-node propagation and lp-node
entailment in a single step, and it pins down that `c5` is entailed in `M*`
rather than being a token in `M`.

---

## If you want to take this further

- **Swap in a real ASP solver.** `DeclarativeLayer.ground()` is the only
  seam — replacing stratified forward chaining with `clingo` buys disjunction,
  unstratified negation, and the paper's full semantics. `pypneu` is the
  reference implementation to read.
- **Norms with deadlines.** N5 is "discharge before termination". Real consumer
  law says "within 14 days", which needs the Event Calculus timeline of §4.2.
- **Mine the net from an event log.** Process mining recovers the AS-IS net from
  the logs you already have, which removes the hand-modelling step this demo
  starts from.
- **Normative positions.** The paper's own motivation is aligning law, its
  implementation as business process, and agent behaviour. Modelling the norms
  deontically (obligation/permission/prohibition with bearers and
  counterparties) is the natural next layer above `Norm.kind`.
