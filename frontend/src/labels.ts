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

/** Decision points (`agentic/handlers.py: DECISION_POINTS`) are named for the
 *  choice they represent, not for a transition, so they are not in NET_LABELS. */
const DECISION_LABELS: Record<string, string> = {
  documents_sufficient: 'Zijn de documenten voldoende?',
  settle_or_assess: 'Direct afhandelen of volledig beoordelen?',
  approve_or_reject: 'Goedkeuren of afwijzen?',
}

/** Dutch name for a place or transition, falling back to whatever the API sent. */
export function netLabel(id: string, fallback: string): string {
  return NET_LABELS[id] ?? fallback
}

/** Dutch name for a decision point, falling back to its id. */
export function decisionLabel(id: string): string {
  return DECISION_LABELS[id] ?? id
}

