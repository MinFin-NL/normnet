/**
 * Subscribes to a run and folds its event stream into something renderable.
 *
 * The server publishes a flat, append-only, index-addressed log. This turns it
 * into the timeline the UI shows: one entry per round, one per model decision,
 * one per norm violation. Folding rather than rendering the raw log matters for
 * the question the page has to answer — *what is happening right now* — because
 * a decision spans three events (asked → answered → committed) and a round
 * spans one event per transition that fired in it.
 */

import { computed, ref, shallowRef } from 'vue'
import { api } from './api'
import type {
  DecisionEntry,
  TransitionActivity,
  PendingDecision,
  RunEvent,
  RunStatus,
  StepEntry,
  TimelineEntry,
} from './types'

export function useRun() {
  const runId = ref<string | null>(null)
  const status = ref<RunStatus>('idle')
  const entries = shallowRef<TimelineEntry[]>([])
  const pending = ref<PendingDecision | null>(null)
  const marking = ref<Record<string, number>>({})
  /** Per transition: is it running right now, has it run, and what did it
   *  produce. This is what the step tracker reads — a reader asking "welke stap
   *  gebeurt er nu?" is asking about the work, not about where a token sits. */
  const activity = ref<Record<string, TransitionActivity>>({})
  const groundAtoms = ref<string[]>([])
  const facts = ref<Record<string, unknown>>({})
  const connectionError = ref<string | null>(null)
  const deciding = ref(false)

  let source: EventSource | null = null
  let cursor = 0
  let retry: number | null = null

  const violations = computed(
    () => entries.value.filter((e): e is Extract<TimelineEntry, { type: 'violation' }> =>
      e.type === 'violation'),
  )
  const finished = computed(
    () => entries.value.find((e): e is Extract<TimelineEntry, { type: 'finish' }> =>
      e.type === 'finish') ?? null,
  )
  const isRunning = computed(
    () => status.value === 'running' || status.value === 'starting',
  )
  /** True only once a run exists — drives the disabled state of the form. */
  const isBusy = computed(
    () => isRunning.value || status.value === 'awaiting_human',
  )

  function markBusy(ids: string[]) {
    const next = { ...activity.value }
    for (const id of ids) {
      next[id] = { ...(next[id] ?? { fired: false, note: '', actor: '' }), busy: true }
    }
    activity.value = next
  }

  function markFired(id: string, note: string, actor: string) {
    activity.value = { ...activity.value, [id]: { busy: false, fired: true, note, actor } }
  }

  function setMarking(next: Record<string, number>) {
    marking.value = { ...next }
  }

  function push(entry: TimelineEntry) {
    entries.value = [...entries.value, entry]
  }
  function replace(index: number, entry: TimelineEntry) {
    const next = entries.value.slice()
    next[index] = entry
    entries.value = next
  }

  /** The most recent decision entry still waiting on an answer. */
  function openDecisionIndex(round: number, decisionId: string): number {
    for (let i = entries.value.length - 1; i >= 0; i--) {
      const e = entries.value[i]
      if (e.type === 'decision' && e.round === round && e.decisionId === decisionId) return i
    }
    return -1
  }

  function apply(event: RunEvent) {
    const d = event.data as any
    switch (event.kind) {
      case 'run_started':
        setMarking(d.initial_marking ?? {})
        break

      case 'round_started': {
        setMarking(d.marking ?? {})
        groundAtoms.value = d.ground_atoms ?? []
        markBusy((d.dispatch ?? []).map((t: any) => t.id))
        const step: StepEntry = {
          type: 'step',
          seq: event.seq,
          round: d.round,
          concurrent: d.concurrent,
          transitions: (d.dispatch ?? []).map((t: any) => ({
            id: t.id,
            label: t.label,
            actor: t.actor,
            autonomy: t.autonomy,
            tools: t.tools ?? [],
            note: '',
            hours: t.hours,
            factsLearned: {},
            consumes: [],
            produces: [],
          })),
        }
        push(step)
        break
      }

      case 'transition_fired': {
        // Fill in the result on the round this transition belongs to.
        for (let i = entries.value.length - 1; i >= 0; i--) {
          const e = entries.value[i]
          if (e.type !== 'step' || e.round !== d.round) continue
          const idx = e.transitions.findIndex((t) => t.id === d.id)
          if (idx === -1) continue
          const transitions = e.transitions.slice()
          transitions[idx] = {
            ...transitions[idx],
            note: d.note_nl || d.note || '',
            factsLearned: d.facts_learned ?? {},
            consumes: d.consumes ?? [],
            produces: d.produces ?? [],
          }
          replace(i, { ...e, transitions })
          break
        }
        markFired(d.id, d.note_nl || d.note || '', d.actor ?? '')
        facts.value = { ...facts.value, ...(d.facts_learned ?? {}) }
        break
      }

      case 'decision_requested':
        push({
          type: 'decision',
          seq: event.seq,
          round: d.round,
          decisionId: d.decision_id,
          options: d.options ?? [],
          systemPrompt: d.system_prompt ?? '',
          userPrompt: d.user_prompt ?? '',
          facts: d.facts ?? {},
          backend: d.backend ?? '',
          choice: null,
          choiceLabel: '',
          rationale: '',
          confidence: 0,
          source: '',
          elapsedMs: 0,
          awaitingHuman: false,
        } satisfies DecisionEntry)
        break

      case 'decision_made': {
        const i = openDecisionIndex(d.round, d.decision_id)
        if (i === -1) break
        const e = entries.value[i] as DecisionEntry
        replace(i, {
          ...e,
          choice: d.choice,
          choiceLabel: d.label ?? d.choice,
          rationale: d.rationale_nl || d.rationale || '',
          confidence: d.confidence ?? 0,
          source: d.source ?? '',
          elapsedMs: d.elapsed_ms ?? 0,
        })
        break
      }

      case 'awaiting_human': {
        pending.value = d as PendingDecision
        status.value = 'awaiting_human'
        const i = openDecisionIndex(d.round, d.decision_id)
        if (i !== -1) {
          replace(i, { ...(entries.value[i] as DecisionEntry), awaitingHuman: true })
        }
        break
      }

      case 'human_decided': {
        pending.value = null
        deciding.value = false
        if (status.value === 'awaiting_human') status.value = 'running'
        const i = openDecisionIndex(d.round, d.decision_id)
        if (i !== -1) {
          const e = entries.value[i] as DecisionEntry
          replace(i, {
            ...e,
            awaitingHuman: false,
            human: {
              choice: d.choice,
              label: d.label ?? d.choice,
              overrode: !!d.overrode,
              recommendation: d.recommendation,
            },
          })
        }
        break
      }

      case 'human_timeout':
        pending.value = null
        deciding.value = false
        status.value = 'running'
        push({ type: 'error', seq: event.seq, message: d.message })
        break

      case 'violation':
        push({
          type: 'violation',
          seq: event.seq,
          round: d.round,
          normId: d.norm_id,
          kind: d.kind,
          // The engine's finding is English; the Dutch rendering travels with
          // the norm and is what this page shows.
          message: d.message_nl || d.message,
        })
        break

      case 'run_finished':
        setMarking(d.marking ?? {})
        facts.value = { ...(d.facts ?? {}) }
        status.value = 'done'
        push({
          type: 'finish',
          seq: event.seq,
          outcome: d.outcome,
          completed: d.completed,
          compliant: d.compliant,
          elapsedHours: d.elapsed_hours,
          humanTouches: d.human_touches,
          handoffs: d.handoffs,
          replayOk: d.replay_ok,
          replayMessage: d.replay_message,
          firingSequence: d.firing_sequence ?? [],
          marking: d.marking ?? {},
        })
        break

      case 'run_error':
        status.value = 'error'
        push({ type: 'error', seq: event.seq, message: d.message })
        break
    }
    cursor = Math.max(cursor, event.seq + 1)
  }

  function connect(id: string) {
    close()
    // Resume from the cursor rather than the start. EventSource reconnects on
    // its own but always to the original URL, which would replay the whole run
    // — so reconnection is driven here instead.
    source = new EventSource(`/api/runs/${id}/stream?from=${cursor}`)

    const onEvent = (e: MessageEvent) => {
      connectionError.value = null
      try {
        apply(JSON.parse(e.data) as RunEvent)
      } catch {
        /* a malformed frame must not kill the stream */
      }
    }
    for (const kind of [
      'run_started', 'round_started', 'transition_fired', 'decision_requested',
      'decision_made', 'awaiting_human', 'human_decided', 'human_timeout',
      'violation', 'run_finished', 'run_error',
    ]) {
      source.addEventListener(kind, onEvent as EventListener)
    }
    source.addEventListener('closed', () => close())
    source.onerror = () => {
      close()
      if (status.value === 'done' || status.value === 'error') return
      connectionError.value = 'Verbinding verbroken — opnieuw verbinden…'
      retry = window.setTimeout(() => connect(id), 1500)
    }
  }

  function close() {
    if (retry !== null) {
      window.clearTimeout(retry)
      retry = null
    }
    source?.close()
    source = null
  }

  async function start(body: {
    scenario: string
    backend: string
    variant: string
    human_in_the_loop: boolean
    pressure: string
  }) {
    close()
    entries.value = []
    pending.value = null
    marking.value = {}
    activity.value = {}
    groundAtoms.value = []
    facts.value = {}
    connectionError.value = null
    cursor = 0
    status.value = 'starting'

    const { run_id } = await api.startRun(body)
    runId.value = run_id
    connect(run_id)
  }

  async function decide(choice: string) {
    if (!runId.value) return
    deciding.value = true
    try {
      await api.decide(runId.value, choice)
      // `human_decided` arriving on the stream is what actually clears the
      // pending state — this only unsticks the button if the post failed.
    } catch (err) {
      deciding.value = false
      connectionError.value = err instanceof Error ? err.message : String(err)
    }
  }

  return {
    runId, status, entries, pending, marking, activity, groundAtoms, facts,
    connectionError, deciding, violations, finished, isRunning, isBusy,
    start, decide, close,
  }
}
