# Roadmap

Planned features, most-developed first. A feature earns a place here once the
design question is settled enough that the remaining work is implementation.
Each entry states what it buys the *audit*, not just the process — a feature
that makes the process faster but the trace weaker does not belong in NormNet.

| # | Feature | State | Buys |
|---|---|---|---|
| 1 | [Outbound notification](#1-outbound-notification-teams-or-email) | planned | the process can speak to people outside the inspector |
| 2 | [Remote decision](#2-remote-decision-approving-from-teams-or-a-mailbox) | planned | the human gate leaves the demo UI and lands where the work is |

---

## 1. Outbound notification (Teams **or** email)

**A transition that tells a person what the process decided — over whichever
channel that person is reachable on.**

Fire-and-forget. No reply is read, nothing blocks. Two channels ship together
because the moment there is one there will be two, and the difference between
them turns out to be a hundred lines at the very edge of the system: the net,
the handler, the norms and the trace do not know which one was used.

### Why it is a transition, not a line in an existing handler

Every handler in `agentic/handlers.py` is a pure function: claim + facts in,
facts out. That is why a run replays. Reaching the outside world touches state
this repo cannot re-derive, and a side effect hidden inside `_payout` would be
invisible to the trace, to the graph view and to the norms — the three things
this repo exists to keep honest. So it gets its own place in the net:

```python
# process/claims.py, to_be_net()
_t("t_notify", "Notify the customer of the outcome",
   ["p_approved"], ["p_notified"],
   agent="comms_agent", autonomy="auto", seconds=2,
   tools=["notify"], side_effect="external",
   audience="customer", added_in_to_be=True),
```

Three things fall out of that, none of which need new machinery:

* the arc from `p_approved` makes it **structurally impossible** to announce
  the approval of a claim that was rejected — the same argument as the
  AND-join, applied to outbound communication;
* the step appears in `log`, in the mermaid export and in the autonomy
  accounting, so "the bot messaged someone" is a first-class event, not a log
  line;
* a norm can quantify over it (below).

Note what the transition does **not** say: no channel, no address. It names an
*audience*. Which is the next section.

### Routing: audience → channel + recipient

Putting `laurens@example.com` in the net would be wrong twice over. It is a
policy decision masquerading as process structure, and it would embed personal
data in every trace, mermaid export and audit transcript the repo produces.

So the net names a role and a routing table resolves it, in one place:

```python
# process/routing.py
ROUTES = {
    "customer":       Route(channel="email", to=lambda claim: claim.contact_email),
    "claims_manager": Route(channel="teams", to="19:...@thread.tacv2"),
    "fraud_desk":     Route(channel="email", to="fraud@example.com"),
}
```

Same reasoning as `process/norms.py`: written once, so the thing the process
does and the thing the auditor checks cannot drift apart. Changing where a
notification lands becomes a config change, not a net change — and a net change
is exactly what should require justifying.

### One message, two renderers

The handler builds a channel-agnostic message; each sink renders it:

```python
@dataclass
class Notification:
    subject: str
    body: str                 # markdown
    fields: dict[str, str]    # the case facts worth showing
    dedupe_key: str

class Notifier(Protocol):
    def send(self, to: str, msg: Notification) -> str: ...   # -> message id

class NullNotifier:           # the default
    def send(self, to, msg) -> str: return "dry-run"
```

`TeamsNotifier` renders an Adaptive Card. `EmailNotifier` renders HTML plus a
plain-text alternative. Neither is visible to the handler, and both are
injected the way `backend` and `emit` already are — the 73 tests run with no
model and must keep running with no network. Channel unconfigured ⇒
`NullNotifier`, and the handler's `note` says so out loud: a dry run must never
read as a delivered message.

### Transport — Teams

| Option | Cost | When it is the right one |
|---|---|---|
| Power Automate workflow webhook | minutes, no AAD app | channel posts — the default |
| Graph `POST /teams/{id}/channels/{id}/messages` | AAD app + app-only `ChannelMessage.Send`, a **protected API** needing Microsoft approval | you already have the approval |
| Azure Bot Service / Bot Framework | Azure resource, app manifest, tenant upload | 1:1 DMs, and mandatory for §2 |

Start with the Power Automate workflow webhook: an HTTPS URL obtained by
clicking through Teams. The retired Office 365 *Incoming Webhook* connector
(`outlook.office.com/webhook/…`) is not an option; tutorials using it are stale.

### Transport — email

| Option | Cost | When it is the right one |
|---|---|---|
| **Graph `POST /users/{id}/sendMail`** | AAD app + `Mail.Send` application permission | the default when the tenant is already M365 — same app registration as Teams |
| SMTP (`aiosmtplib`, or MailHog locally) | none | dev, and any non-Microsoft deployment |
| Azure Communication Services Email | ACS resource + verified domain | high volume, or mail that must not come from a person's mailbox |

Two things to get right on the Graph route:

* `Mail.Send` as an *application* permission grants send-as-anybody across the
  tenant. Scope it with an **application access policy** so the app can only
  send from the one service mailbox. Ask for this at request time — retrofitting
  it after a security review is the slow path.
* Send from a mailbox that visibly belongs to the process
  (`claims-bot@…`), never a person's. A refund decision that appears to come
  from a named employee's mailbox is a mess for both the recipient and the audit.

### Idempotency

The scheduler loops — `MAX_ROUNDS = 40`, and `p_await_docs → p_registered` is a
genuine cycle. Carry `f"{claim.claim_id}:{tid}:{round}"` as the `dedupe_key`
and have the sink drop repeats. Teams forgives a duplicate post; a customer
receiving the same refund mail three times does not.

### Norms

The channel-independent prohibition on speaking too early:

```prolog
N_notify :- fired:t_notify, not decision_committed.
```

*Never announce an outcome the process has not committed to.* Written once in
`process/norms.py`, and thereby also the comms agent's instruction and the
auditor's criterion.

Email earns a second one worth having. `customer_pressure` is carried in the
case file precisely because it is *said*, not evidenced — and it must not be
quoted back out of the building:

```prolog
N_leak :- fired:t_notify, audience:customer, body_cites:customer_pressure.
```

### Emit

`emit("external_message", {channel, to_redacted, subject, body, …})` carrying
the rendered body. For a demo about auditability, the literal text a bot put in
front of a human is close to the most interesting event on the stream — the
inspector should show it, with the recipient redacted to a role.

### Tasks

1. `p_notified` place + `t_notify` transition in `to_be_net()`; AS-IS keeps
   `t_close_paid` (a person mailing the customer) so the topology comparison
   still means something.
2. `Notification`, `Notifier`, `NullNotifier`, `RecordingNotifier` (tests).
3. `process/routing.py` with `ROUTES`; `contact_email` on `Claim`.
4. `TeamsNotifier` (webhook + Adaptive Card) and `EmailNotifier` (Graph, with
   SMTP fallback for dev).
5. `_notify` handler + registry entry; dedupe key in facts.
6. Wire notifier + routes through `CompiledProcess.__init__` → `RunSession`.
7. `N_notify` and `N_leak` in `process/norms.py`.
8. `external_message` event, rendered in the inspector.
9. Tests: dry-run by default; sink called once per outcome; both renderers
   asserted against one `Notification`; routing resolves audience → recipient;
   both norms fire when provoked.

---

## 2. Remote decision (approving from Teams **or** a mailbox)

**The approve/reject gate moves out of the React UI and to wherever the
approver already is.**

`RunSession._gate` (`server/runner.py:75`) is already the right object: it
blocks the worker on a `threading.Event`, times out, and exposes
`decide(choice)` for a transport to call. A remote gate is that same object
with a different front end — `awaiting_human` (`agentic/compile.py:241`)
already emits exactly the payload a card or a mail needs: options,
recommendation, rationale, confidence, claim, facts.

Unlike §1, the two channels are **not** symmetric here. Teams has a real
interactive surface; email does not.

### Teams

**Power Automate, "Post adaptive card and wait for a response".** The flow owns
the card, the identity and the update-in-place. `_gate` calls its HTTP trigger
and blocks on the response. Cheapest by a wide margin; the cost is a timeout
ceiling you do not control and no custom card behaviour. **Start here.**

**Azure Bot Service + Bot Framework**, when the flow is not enough:

1. Register the bot → app ID/secret, messaging endpoint `/api/messages`.
   Deployment already goes to Azure (`azure-pipelines.yml`), so this fits.
2. Teams app manifest, sideloaded or admin-uploaded — usually the slowest step,
   for tenant-policy reasons rather than technical ones.
3. **Proactive messaging needs a stored `ConversationReference`.** A bot cannot
   message first out of nowhere; capture the reference when someone installs the
   app or @-mentions the bot, and persist it. This is the step that catches
   people out.
4. Card with `Action.Execute`, `data: {run_id, decision_id, choice}`.
5. `/api/messages` validates the Bot Framework JWT, then calls
   `registry.get(run_id).decide(choice)`. The existing `choice not in allowed`
   check already handles a stale card being clicked.
6. Update the card in place, so the second clicker sees "already decided by …"
   rather than a silent no-op.

### Email — signed links, not buttons

Outlook Actionable Messages can put real buttons in a mail, but they need
provider registration, they render inertly in every other client, and many
tenants strip them. Do not build the gate on them.

Instead the mail carries two **signed magic links** back to the inspector:

```
/decide/{token}     token = HMAC(run_id, decision_id, choice, exp, nonce)
```

* short expiry, tied to `HUMAN_GATE_TIMEOUT_S`, single-use via the nonce;
* the link opens a **confirmation page** showing the case, and the decision is
  committed by a click on that page — never by the mail client fetching the URL.
  A one-click-approve link is both a phishing-shaped affordance and something
  a link-prefetching scanner will trigger on its own;
* the page requires a sign-in when one is available, so `human_decided` can
  record *who*, not merely *that*.

An email gate is the weaker of the two and the doc should keep saying so: it
authenticates a token, whereas Teams authenticates a person.

### Two decisions to take before writing code

**The timeout must not quietly approve refunds.** Today, no answer within
`HUMAN_GATE_TIMEOUT_S` means the agent's recommendation stands and the run is
no longer human-in-the-loop. In the inspector that lapse is on screen. A card
nobody clicked at 18:00 on a Friday is not, and an unread mail even less so.
The remote gate should **fail closed**, or at minimum send a follow-up
recording that the gate lapsed.

**`human_in_the_loop` must not become a claim we cannot back up.** It is set
from `human_gate is not None` (`agentic/compile.py:426`). If a Power Automate
flow can answer on its own, or a mail scanner can trip a link, that boolean
starts asserting something no person did — precisely the drift this repo was
built to catch. Replace it with `gate: "ui" | "teams" | "email" | "none"`,
record the deciding identity in `human_decided`, and let the auditor treat the
channels as the different grades of evidence they are. "A human committed
this" becomes "*this* human committed this, at this time, over this channel" —
the audit payoff that makes §2 worth more than its convenience.
