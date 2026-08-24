import type { ExecutorKind } from './types'

/** Dutch labels for the snake_case keys the engine writes into the case file
 *  (`agentic/handlers.py`). The engine names them for the norms that read them,
 *  not for a reader — so the simple view translates, and anything not in this
 *  map is treated as an internal field and only shown in technical mode. */

const FACT_LABELS: Record<string, string> = {
  amount_eur: 'Schadebedrag',
  in_warranty: 'Binnen garantie',
  has_receipt: 'Bon aanwezig',
  prior_claims_12m: 'Eerdere claims (12 mnd)',
  customer_risk: 'Klantrisico',
  docs_requests: 'Keer documenten opgevraagd',
  customer_pressure: 'Extra bericht van de klant',
  evidence: 'Bewijsstukken',
  fraud_score: 'Fraudescore',
  coverage_ok: 'Gedekt door garantie',
  settlement: 'Afhandeling',
  paid_eur: 'Uitbetaald bedrag',
}

/** Enumerated fact values the engine writes in English. */
const VALUE_LABELS: Record<string, string> = {
  high: 'hoog',
  low: 'laag',
  complete: 'compleet',
  partial: 'gedeeltelijk',
  incomplete: 'onvolledig',
  waived: 'niet nodig',
  auto: 'direct afgehandeld',
}

export function isKnownFact(key: string): boolean {
  return key in FACT_LABELS
}

export function factLabel(key: string): string {
  return FACT_LABELS[key] ?? key
}

export function factValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'ja' : 'nee'
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string' && value in VALUE_LABELS) return VALUE_LABELS[value]
  return String(value)
}

/** Dutch display names for the net's places and transitions. The engine names
 *  them in English — it is shared with the CLI, `docs/*.mmd` and the paper
 *  mapping in `docs/LPPN.md`, all of which are English — but this UI is Dutch,
 *  so the translation belongs here rather than in `process/claims.py`. Keyed on
 *  the ids, which are stable and shared between the as-is and to-be nets.
 *  Anything missing falls back to the label the API sent. */
const NET_LABELS: Record<string, string> = {
  // places
  p_intake: 'Claim ingediend',
  p_registered: 'Claim geregistreerd',
  p_await_docs: 'Wacht op documenten',
  p_docs_ok: 'Documenten compleet',
  p_fraud_todo: 'Fraudecontrole open',
  p_cover_todo: 'Garantiecontrole open',
  p_fraud_done: 'Fraudecontrole gedaan',
  p_cover_done: 'Garantiecontrole gedaan',
  p_assessed: 'Beoordeling afgerond',
  p_approved: 'Goedgekeurd',
  p_rejected: 'Afgewezen',
  p_paid: 'Vergoeding uitbetaald',
  p_closed: 'Zaak gesloten',
  // transitions
  t_register: 'Claim registreren en triëren',
  t_auto_resolve: 'Klein bedrag direct afhandelen',
  t_request_docs: 'Documenten opvragen',
  t_docs_received: 'Documenten accepteren',
  t_docs_rejected: 'Documenten onvolledig → opnieuw opvragen',
  t_split_checks: 'Fraude- en garantiecontrole starten',
  t_fraud_check: 'Fraudecontrole',
  t_coverage_check: 'Garantiecontrole',
  t_assess: 'Claim beoordelen',
  t_approve: 'Goedkeuren',
  t_reject: 'Afwijzen',
  t_issue_refund: 'Vergoeding uitbetalen',
  t_close_paid: 'Klant informeren en afsluiten',
  t_close_rejected: 'Afwijzing versturen en afsluiten',
}

/** Who does the work. The net names its actors with agent ids (`intake_agent`)
 *  or, in the as-is model, with English department names — neither is something
 *  to put in front of a reader. */
const ACTOR_LABELS: Record<string, string> = {
  intake_agent: 'Intake-agent',
  triage_agent: 'Triage-agent',
  evidence_agent: 'Bewijs-agent',
  orchestrator: 'Orkestrator',
  fraud_agent: 'Fraude-agent',
  coverage_agent: 'Garantie-agent',
  assessor_agent: 'Beoordelings-agent',
  payment_agent: 'Betaal-agent',
  comms_agent: 'Communicatie-agent',
  // as-is owners, for completeness — the inspector shows the to-be net
  'Service desk': 'Servicedesk',
  'Claims lead': 'Teamleider claims',
  'Fraud analyst': 'Fraudeanalist',
  'Warranty specialist': 'Garantiespecialist',
  'Claims manager': 'Claimsmanager',
  Finance: 'Financiën',
}

export function actorLabel(actor: string): string {
  return ACTOR_LABELS[actor] ?? actor
}

/** The process as a reader follows it: the *activities*, in order.
 *
 *  Deliberately keyed on transitions rather than places. A place is a state the
 *  case sits in ("documenten compleet"); a reader asking "welke stap gebeurt
 *  er nu?" means the work, and the work is a transition. Steps in the same
 *  `phase` happen together (the two checks) or are alternatives to one another
 *  (goedkeuren / afwijzen) — that is what makes it possible to say that a step
 *  was *overgeslagen* rather than leaving it hanging as "nog te doen" forever.
 *
 *  `t_split_checks` has no entry: it is bookkeeping for the AND-split, not a
 *  step anyone performs. */
export interface ProcessStep {
  key: string
  label: string
  /** firing any of these completes the step */
  transitions: string[]
  /** steps that happen at the same point in the process share a phase */
  phase: number
  /** `parallel`: happens alongside its phase siblings.
   *  `branch`: only one of its phase siblings is taken. */
  kind?: 'parallel' | 'branch'
}

export const PROCESS_STEPS: readonly ProcessStep[] = [
  { key: 'register', label: 'Claim registreren en triëren', transitions: ['t_register'], phase: 1 },
  { key: 'auto', label: 'Direct afhandelen', transitions: ['t_auto_resolve'], phase: 2, kind: 'branch' },
  { key: 'docs', label: 'Documenten opvragen', transitions: ['t_request_docs'], phase: 2, kind: 'branch' },
  { key: 'docs_check', label: 'Documenten beoordelen', transitions: ['t_docs_received'], phase: 3 },
  { key: 'fraud', label: 'Fraudecontrole', transitions: ['t_fraud_check'], phase: 4, kind: 'parallel' },
  { key: 'coverage', label: 'Garantiecontrole', transitions: ['t_coverage_check'], phase: 4, kind: 'parallel' },
  { key: 'assess', label: 'Claim beoordelen', transitions: ['t_assess'], phase: 5 },
  { key: 'approve', label: 'Goedkeuren', transitions: ['t_approve'], phase: 6, kind: 'branch' },
  { key: 'reject', label: 'Afwijzen', transitions: ['t_reject'], phase: 6, kind: 'branch' },
  { key: 'pay', label: 'Vergoeding uitbetalen', transitions: ['t_issue_refund'], phase: 7 },
  { key: 'close', label: 'Klant informeren en afsluiten', transitions: ['t_close_paid', 't_close_rejected'], phase: 8 },
]

/** Decision points (`agentic/handlers.py: DECISION_POINTS`) are named for the
 *  choice they represent, not for a transition, so they are not in NET_LABELS. */
const DECISION_LABELS: Record<string, string> = {
  documents_sufficient: 'Zijn de documenten voldoende?',
  settle_or_assess: 'Direct afhandelen of volledig beoordelen?',
  approve_or_reject: 'Goedkeuren of afwijzen?',
}

/** Short Dutch names for the scenarios. The API sends the full claim — id,
 *  English product name and amount — which is far too long for the select in a
 *  24rem sidebar: it pushed the control past the edge of the panel. The details
 *  are shown under the select instead, where they can wrap. */
const SCENARIO_LABELS: Record<string, string> = {
  standard: 'Koptelefoon',
  micro: 'USB-C-kabel',
  out_of_warranty: 'Monitor',
  pressure: 'Laptoplader',
}

export function scenarioLabel(id: string, fallback: string): string {
  return SCENARIO_LABELS[id] ?? fallback
}

/** Dutch name for a place or transition, falling back to whatever the API sent. */
export function netLabel(id: string, fallback: string): string {
  return NET_LABELS[id] ?? fallback
}

/** Dutch name for a decision point, falling back to its id. */
export function decisionLabel(id: string): string {
  return DECISION_LABELS[id] ?? id
}


/* ── Who performs a step ─────────────────────────────────────────────────── */

/** The three kinds of executor, in the words a reader needs. This is the
 *  distinction the whole inspector is built to make visible: a step is either
 *  vastgelegde code, een taalmodel dat oordeelt, or een mens die tekent. */
export interface ExecutorMeta {
  label: string
  short: string
  icon: string
  /** one line, for a tooltip and the legend */
  explanation: string
  /** the same thing at a glance, for the compact legend that stays on screen
   *  while a run is playing — the long form is a lecture nobody re-reads */
  oneLiner: string
}

export const EXECUTORS: Record<ExecutorKind, ExecutorMeta> = {
  deterministic: {
    label: 'Vastgelegde regel',
    short: 'Regel',
    icon: '⚙',
    explanation:
      'Uitgevoerd door code die is vastgelegd: dezelfde invoer geeft altijd dezelfde uitkomst. Geen taalmodel, geen mens.',
    oneLiner: 'Code. Zelfde invoer, zelfde uitkomst.',
  },
  llm: {
    label: 'Taalmodel',
    short: 'Model',
    icon: '◆',
    explanation:
      'Hier had het proces meerdere toegestane vervolgstappen. Een taalmodel heeft gekozen en die keuze gemotiveerd.',
    oneLiner: 'Meer dan één stap mocht. Het model koos — en motiveert.',
  },
  human: {
    label: 'Mens',
    short: 'Mens',
    icon: '☻',
    explanation:
      'Een mens neemt dit besluit. Het proces staat hier werkelijk stil tot er iemand tekent.',
    oneLiner: 'Het proces staat stil tot ú tekent.',
  },
}

export function executorMeta(kind: ExecutorKind): ExecutorMeta {
  return EXECUTORS[kind] ?? EXECUTORS.deterministic
}
