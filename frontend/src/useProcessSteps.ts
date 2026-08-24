/**
 * The process as a reader follows it, with a state per step.
 *
 * Extracted so there is exactly one answer to "which step is this case on".
 * It used to live inside the sidebar tracker; the rail in the process bar needs
 * the same derivation, and two copies of this logic would drift the moment
 * anyone touched the skip rules.
 */

import { computed, type Ref } from 'vue'
import { PROCESS_STEPS } from './labels'
import type { ExecutorKind, NetShape, TransitionActivity } from './types'

export type StepState = 'done' | 'busy' | 'waiting-human' | 'skipped' | 'todo'

export const STATE_TEXT: Record<StepState, string> = {
  done: 'Afgerond',
  busy: 'Bezig',
  'waiting-human': 'Wacht op uw besluit',
  skipped: 'Overgeslagen',
  todo: 'Nog niet aan de beurt',
}

export interface PhaseGroup {
  phase: number
  steps: DerivedStep[]
  state: StepState
  /** position on the route this case takes; 0 for a phase that was skipped */
  number: number
}

export interface DerivedStep {
  key: string
  label: string
  transitions: string[]
  phase: number
  kind?: 'parallel' | 'branch'
  executor: ExecutorKind
  llmAdvises: boolean
  state: StepState
  /** position on the route this case actually takes; 0 for a skipped step */
  number: number
  note: string
  actor: string
}

export function useProcessSteps(
  net: Ref<NetShape>,
  activity: Ref<Record<string, TransitionActivity>>,
  gated: Ref<string[]>,
) {
  const byId = computed(() => new Map(net.value.transitions.map((t) => [t.id, t])))

  /** A step is done when one of its transitions has fired, busy while one is
   *  running, and *skipped* once the process has moved past its phase without
   *  it — which is how the auto-settle short cut and the untaken side of
   *  approve/reject stop reading as work that is still to come. */
  const steps = computed<DerivedStep[]>(() => {
    const fired = (step: { transitions: string[] }) =>
      step.transitions.find((t) => activity.value[t]?.fired)

    const maxDonePhase = PROCESS_STEPS.reduce(
      (max, step) => (fired(step) ? Math.max(max, step.phase) : max),
      0,
    )

    let position = 0
    return PROCESS_STEPS.map((step) => {
      const doneVia = fired(step)
      const busy = step.transitions.some((t) => activity.value[t]?.busy)
      const isGated = step.transitions.some((t) => gated.value.includes(t))
      const siblingTaken =
        step.kind === 'branch' &&
        PROCESS_STEPS.some(
          (other) => other.phase === step.phase && other.key !== step.key && fired(other),
        )

      const state: StepState = doneVia
        ? 'done'
        : isGated
          ? 'waiting-human'
          : busy
            ? 'busy'
            : siblingTaken || step.phase < maxDonePhase
              ? 'skipped'
              : 'todo'

      const info = doneVia ? activity.value[doneVia] : undefined
      // The step that was actually taken, or — for a step still ahead — the
      // first of its alternatives, which is enough to say who performs it.
      const shape = byId.value.get(doneVia ?? step.transitions[0])
      return {
        ...step,
        executor: (shape?.executor ?? 'deterministic') as ExecutorKind,
        llmAdvises: !!shape?.llm_advises,
        state,
        number: state === 'skipped' ? 0 : (position += 1),
        note: state === 'done' ? (info?.note ?? '') : '',
        actor:
          info?.actor ??
          step.transitions.map((t) => activity.value[t]?.actor).find(Boolean) ??
          '',
      }
    })
  })

  /** The steps grouped as the net actually branches: one column per phase.
   *  A phase holds one step, or two that happen at once (the AND-split), or
   *  two that are alternatives (the exclusive choice). Rendering the eleven
   *  steps as eleven columns both overflows the page and misrepresents the
   *  process — it shows approve *and* reject as things that will both happen. */
  const phases = computed<PhaseGroup[]>(() => {
    const out: PhaseGroup[] = []
    for (const step of steps.value) {
      const last = out[out.length - 1]
      if (last && last.phase === step.phase) last.steps.push(step)
      else out.push({ phase: step.phase, steps: [step], state: 'todo', number: 0 })
    }
    let position = 0
    for (const group of out) {
      const has = (state: StepState) => group.steps.some((s) => s.state === state)
      group.state = has('waiting-human')
        ? 'waiting-human'
        : has('busy')
          ? 'busy'
          : has('done')
            ? 'done'
            : group.steps.every((s) => s.state === 'skipped')
              ? 'skipped'
              : 'todo'
      group.number = group.state === 'skipped' ? 0 : (position += 1)
    }
    return out
  })

  const doneCount = computed(() => phases.value.filter((p) => p.state === 'done').length)
  /** Counted in phases, and skipped phases left out: approve and reject are
   *  two rows but one step of the process, and counting a phase this case never
   *  entered would say "4 van 8" for a claim that only ever had five. */
  const plannedCount = computed(
    () => phases.value.filter((p) => p.state !== 'skipped').length,
  )
  const percent = computed(() =>
    plannedCount.value ? Math.round((doneCount.value / plannedCount.value) * 100) : 0,
  )
  /** What is happening right now: the step being executed, the one the run is
   *  blocked on, or — when neither — the last one that finished. */
  const current = computed<DerivedStep | null>(() => {
    const route = steps.value.filter((s) => s.state !== 'skipped')
    return (
      route.find((s) => s.state === 'waiting-human') ??
      route.find((s) => s.state === 'busy') ??
      [...route].reverse().find((s) => s.state === 'done') ??
      null
    )
  })

  return { steps, phases, doneCount, plannedCount, percent, current }
}
