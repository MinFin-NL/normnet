<template>
  <div class="normnet-tracker">
    <!-- Progress at a glance, before the detail: how far along is this case. -->
    <div class="normnet-tracker__summary">
      <p class="normnet-tracker__count">
        <strong>{{ doneCount }}</strong> van {{ plannedCount }} stappen gedaan
      </p>
      <div
        class="normnet-tracker__bar"
        role="progressbar"
        :aria-valuenow="doneCount"
        aria-valuemin="0"
        :aria-valuemax="plannedCount"
        :aria-label="`${doneCount} van ${plannedCount} processtappen afgerond`"
      >
        <span class="normnet-tracker__bar-fill" :style="{ inlineSize: `${percent}%` }" />
      </div>
    </div>

    <ol class="normnet-tracker__list">
      <li
        v-for="(step, i) in steps"
        :key="step.key"
        class="normnet-tracker__step"
        :class="[
          `is-${step.state}`,
          step.kind ? `is-${step.kind}` : '',
          { 'is-phase-start': i > 0 && step.phase !== steps[i - 1].phase },
        ]"
      >
        <span class="normnet-tracker__marker" aria-hidden="true">
          <span class="normnet-tracker__dot">
            <svg
              v-if="step.state === 'done'"
              class="normnet-tracker__glyph"
              viewBox="0 0 16 16"
            >
              <path
                d="M3.5 8.5l3 3 6-7"
                fill="none"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span v-else-if="step.state === 'busy'" class="normnet-tracker__spinner" />
            <span v-else-if="step.state === 'waiting-human'" class="normnet-tracker__bang">!</span>
            <span v-else-if="step.state === 'skipped'" class="normnet-tracker__skip">–</span>
            <span v-else class="normnet-tracker__num">{{ step.number }}</span>
          </span>
        </span>

        <div class="normnet-tracker__body">
          <p class="normnet-tracker__label">
            {{ step.label }}
            <span v-if="step.kind === 'parallel'" class="normnet-tracker__tag">tegelijk</span>
            <span v-else-if="step.kind === 'branch'" class="normnet-tracker__tag">of</span>
          </p>

          <p v-if="step.state === 'todo'" class="normnet-visually-hidden">
            {{ STATE_TEXT.todo }}
          </p>
          <p v-else class="normnet-tracker__state">
            <span class="normnet-tracker__state-text">{{ STATE_TEXT[step.state] }}</span>
            <template v-if="step.actor && step.state !== 'skipped'">
              · {{ actorLabel(step.actor) }}
            </template>
          </p>

          <p v-if="step.note" class="normnet-tracker__note">{{ step.note }}</p>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { actorLabel, PROCESS_STEPS } from '../labels'
import type { TransitionActivity } from '../types'

const props = defineProps<{
  /** per transition id: running, finished, and what it produced */
  activity: Record<string, TransitionActivity>
  /** transitions the run is currently blocked on, waiting for a person */
  gated: string[]
}>()

type StepState = 'done' | 'busy' | 'waiting-human' | 'skipped' | 'todo'

const STATE_TEXT: Record<StepState, string> = {
  done: 'Afgerond',
  busy: 'Bezig',
  'waiting-human': 'Wacht op uw besluit',
  skipped: 'Overgeslagen',
  todo: 'Nog niet aan de beurt',
}

/** A step is done when one of its transitions has fired, busy while one is
 *  running, and *skipped* once the process has moved past its phase without it
 *  — which is how the auto-settle short cut and the untaken side of
 *  approve/reject stop reading as work that is still to come. */
const steps = computed(() => {
  const fired = (step: { transitions: string[] }) =>
    step.transitions.find((t) => props.activity[t]?.fired)

  const maxDonePhase = PROCESS_STEPS.reduce(
    (max, step) => (fired(step) ? Math.max(max, step.phase) : max),
    0,
  )

  let position = 0
  return PROCESS_STEPS.map((step) => {
    const doneVia = fired(step)
    const busy = step.transitions.some((t) => props.activity[t]?.busy)
    const gated = step.transitions.some((t) => props.gated.includes(t))
    const siblingTaken =
      step.kind === 'branch' &&
      PROCESS_STEPS.some(
        (other) => other.phase === step.phase && other.key !== step.key && fired(other),
      )

    const state: StepState = doneVia
      ? 'done'
      : gated
        ? 'waiting-human'
        : busy
          ? 'busy'
          : siblingTaken || step.phase < maxDonePhase
            ? 'skipped'
            : 'todo'

    const info = doneVia ? props.activity[doneVia] : undefined
    return {
      ...step,
      state,
      // numbered over the route this case actually takes, so the last number
      // matches the "x van y" above rather than counting skipped steps
      number: state === 'skipped' ? 0 : (position += 1),
      note: state === 'done' ? (info?.note ?? '') : '',
      actor: info?.actor ?? step.transitions.map((t) => props.activity[t]?.actor).find(Boolean) ?? '',
    }
  })
})

const doneCount = computed(() => steps.value.filter((s) => s.state === 'done').length)
/** Skipped steps are not part of *this* case's route — counting them would say
 *  "4 van 11" for a claim that only ever had five steps to take. */
const plannedCount = computed(() => steps.value.filter((s) => s.state !== 'skipped').length)
const percent = computed(() =>
  plannedCount.value ? Math.round((doneCount.value / plannedCount.value) * 100) : 0,
)
</script>

<style scoped>
.normnet-tracker__summary {
  margin-block-end: var(--rvo-space-md, 1rem);
}
.normnet-tracker__count {
  margin: 0 0 0.35rem;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-tracker__count strong {
  color: var(--rvo-color-lintblauw, #154273);
}
.normnet-tracker__bar {
  block-size: 0.375rem;
  border-radius: 999px;
  background: var(--normnet-color-border, #e2e8f0);
  overflow: hidden;
}
.normnet-tracker__bar-fill {
  display: block;
  block-size: 100%;
  border-radius: 999px;
  background: var(--normnet-color-ok, #39870c);
  transition: inline-size 0.4s ease;
}

.normnet-tracker__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* One row per step: a marker column of fixed width, so the connecting line is
   always straight regardless of how much text a step carries. */
.normnet-tracker__step {
  position: relative;
  display: grid;
  grid-template-columns: 1.75rem 1fr;
  gap: 0.65rem;
  padding-block: 0.4rem;
}
.normnet-tracker__step.is-phase-start {
  margin-block-start: 0.15rem;
}
.normnet-tracker__marker {
  position: relative;
  display: flex;
  justify-content: center;
}
/* The line runs from this step's dot to the next one. */
.normnet-tracker__step:not(:last-child) .normnet-tracker__marker::after {
  content: '';
  position: absolute;
  inset-block-start: 1.6rem;
  inset-block-end: -1.05rem;
  inline-size: 2px;
  border-radius: 1px;
  background: var(--normnet-color-border, #e2e8f0);
}
.normnet-tracker__step.is-done:not(:last-child) .normnet-tracker__marker::after {
  background: var(--normnet-color-ok, #39870c);
}

.normnet-tracker__dot {
  position: relative;
  z-index: 1;
  inline-size: 1.5rem;
  block-size: 1.5rem;
  border-radius: 50%;
  border: 2px solid var(--normnet-color-border-strong, #cbd5e1);
  background: var(--normnet-color-surface, #fff);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
}
.normnet-tracker__glyph {
  inline-size: 0.875rem;
  block-size: 0.875rem;
}
.normnet-tracker__num {
  font-size: 0.6875rem;
  font-weight: 700;
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-tracker__skip {
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-tracker__bang {
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--rvo-color-wit, #fff);
}

/* ── per state ─────────────────────────────────────────────────────────── */
.normnet-tracker__step.is-done .normnet-tracker__dot {
  background: var(--normnet-color-ok, #39870c);
  border-color: var(--normnet-color-ok, #39870c);
  color: var(--rvo-color-wit, #fff);
}
.normnet-tracker__step.is-busy .normnet-tracker__dot {
  border-color: var(--rvo-color-hemelblauw, #007bc7);
  box-shadow: 0 0 0 4px rgb(0 123 199 / 0.15);
}
.normnet-tracker__step.is-waiting-human .normnet-tracker__dot {
  background: var(--normnet-color-human, #ffb612);
  border-color: var(--normnet-color-human, #ffb612);
  box-shadow: 0 0 0 4px rgb(255 182 18 / 0.25);
}
.normnet-tracker__step.is-waiting-human .normnet-tracker__bang {
  color: var(--rvo-color-zwart, #000);
}
.normnet-tracker__step.is-skipped .normnet-tracker__dot {
  border-style: dashed;
  background: var(--normnet-color-page-bg, #f1f5f9);
}

.normnet-tracker__spinner {
  inline-size: 0.75rem;
  block-size: 0.75rem;
  border-radius: 50%;
  border: 2px solid var(--rvo-color-hemelblauw, #007bc7);
  border-block-start-color: transparent;
  animation: normnet-spin 0.9s linear infinite;
}
@keyframes normnet-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── text ──────────────────────────────────────────────────────────────── */
.normnet-tracker__body {
  min-inline-size: 0;
  padding-block-start: 0.1rem;
}
.normnet-tracker__label {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-tracker__step.is-done .normnet-tracker__label,
.normnet-tracker__step.is-busy .normnet-tracker__label,
.normnet-tracker__step.is-waiting-human .normnet-tracker__label {
  color: var(--rvo-color-zwart, #12161a);
}
.normnet-tracker__step.is-busy .normnet-tracker__label,
.normnet-tracker__step.is-waiting-human .normnet-tracker__label {
  font-weight: 700;
}
.normnet-tracker__step.is-skipped .normnet-tracker__label {
  font-weight: 400;
}

.normnet-tracker__state {
  margin: 0.1rem 0 0;
  font-size: 0.75rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-tracker__state-text {
  font-weight: 600;
}
.normnet-tracker__step.is-done .normnet-tracker__state-text {
  color: var(--normnet-color-ok, #39870c);
}
.normnet-tracker__step.is-busy .normnet-tracker__state-text {
  color: var(--rvo-color-hemelblauw, #007bc7);
}
.normnet-tracker__step.is-waiting-human .normnet-tracker__state-text {
  color: var(--rvo-color-donkerbruin, #8f5c2c);
}
.normnet-tracker__step.is-todo .normnet-tracker__state,
.normnet-tracker__step.is-skipped .normnet-tracker__state {
  color: var(--normnet-color-text-subtle, #64748b);
}

.normnet-tracker__note {
  margin: 0.25rem 0 0;
  padding: 0.3rem 0.5rem;
  border-inline-start: 2px solid var(--normnet-color-border, #e2e8f0);
  background: var(--normnet-color-page-bg, #f1f5f9);
  border-radius: 0 3px 3px 0;
  font-size: 0.75rem;
  color: var(--normnet-color-text-muted, #4b5563);
  overflow-wrap: anywhere;
}

/* Alternatives and simultaneous work are set in from the spine, so the shape
   of the process — a split, a choice — is visible without reading a word. */
.normnet-tracker__step.is-parallel .normnet-tracker__body,
.normnet-tracker__step.is-branch .normnet-tracker__body {
  padding-inline-start: 0.5rem;
  border-inline-start: 2px solid var(--normnet-color-border, #e2e8f0);
}
.normnet-tracker__tag {
  display: inline-block;
  margin-inline-start: 0.35rem;
  padding: 0.05em 0.4em;
  border-radius: 999px;
  background: var(--normnet-color-page-bg, #f1f5f9);
  border: 1px solid var(--normnet-color-border, #e2e8f0);
  font-size: 0.625rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
  vertical-align: 0.1em;
}
</style>
