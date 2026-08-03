/** Shapes the API sends. Kept close to the Python so a mismatch is obvious. */

export interface RunEvent<T = Record<string, unknown>> {
  seq: number
  /** Envelope kind. The payload is *nested* under `data`, never spread —
   *  a violation's own `kind` would otherwise shadow this one. */
  kind: string
  data: T
}

export interface Scenario {
  id: string
  claim_id: string
  customer: string
  product: string
  amount_eur: number
  purchase_days_ago: number
  warranty_months: number
  in_warranty: boolean
  has_receipt: boolean
  prior_claims_12m: number
  story: string
  customer_pressure: string
}

export interface BackendOption {
  id: string
  label: string
  hint: string
}

export interface NormInfo {
  id: string
  kind: 'prohibition' | 'obligation'
  body: string[]
  message: string
  guidance: string
}

export interface TransitionInfo {
  id: string
  label: string
  actor: string
  autonomy: string
  tools: string[]
  inputs: string[]
  outputs: string[]
}

export interface NetShape {
  name: string
  places: { id: string; label: string; description: string }[]
  transitions: TransitionInfo[]
  initial_marking: Record<string, number>
  final_place: string | null
}

export interface Bootstrap {
  scenarios: Scenario[]
  backends: BackendOption[]
  norms: NormInfo[]
  lp_nodes: { rule: string; note: string }[]
  thresholds: { auto_settle_limit_eur: number; fraud_referral_score: number }
  nets: Record<string, NetShape>
}

export interface PendingDecision {
  round: number
  decision_id: string
  options: string[]
  recommendation: string
  rationale: string
  confidence: number
  labels: Record<string, string>
  gated: string[]
  claim: Record<string, unknown>
  facts: Record<string, unknown>
}

/** `idle` is client-side only: no run has been started yet. The server
 *  never reports it. */
export type RunStatus =
  | 'idle' | 'starting' | 'running' | 'awaiting_human' | 'done' | 'error'

export interface RunSnapshot {
  run_id: string
  status: RunStatus
  scenario: string
  variant: string
  pending: PendingDecision | null
  error: string | null
  events: RunEvent[]
}

/* ── Timeline entries — the view model the UI actually renders ───────────── */

export interface DecisionEntry {
  type: 'decision'
  seq: number
  round: number
  decisionId: string
  options: string[]
  systemPrompt: string
  userPrompt: string
  facts: Record<string, unknown>
  backend: string
  /** Filled in when `decision_made` arrives; null while the model is thinking. */
  choice: string | null
  choiceLabel: string
  rationale: string
  confidence: number
  source: string
  elapsedMs: number
  /** Set when a person committed the step rather than the agent. */
  human?: { choice: string; label: string; overrode: boolean; recommendation: string }
  awaitingHuman: boolean
}

export interface StepEntry {
  type: 'step'
  seq: number
  round: number
  concurrent: boolean
  transitions: {
    id: string
    label: string
    actor: string
    autonomy: string
    tools: string[]
    note: string
    hours: number
    factsLearned: Record<string, unknown>
    consumes: string[]
    produces: string[]
  }[]
}

export interface ViolationEntry {
  type: 'violation'
  seq: number
  round: number
  normId: string
  kind: string
  message: string
}

export interface FinishEntry {
  type: 'finish'
  seq: number
  outcome: string
  completed: boolean
  compliant: boolean
  elapsedHours: number
  humanTouches: number
  handoffs: number
  replayOk: boolean
  replayMessage: string
  firingSequence: string[]
  marking: Record<string, number>
}

export interface ErrorEntry {
  type: 'error'
  seq: number
  message: string
}

export type TimelineEntry =
  | DecisionEntry
  | StepEntry
  | ViolationEntry
  | FinishEntry
  | ErrorEntry
