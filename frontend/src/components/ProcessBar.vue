<template>
  <!-- The subject of the page, at the top of the page.
       This one element answers all four questions a first-time reader has —
       what is this (a claim, in eight steps), where are we, who does each step,
       and what happens next — and it is the same element before, during and
       after a run, so nothing the reader learns disappears on them. -->
  <section class="normnet-pb" :class="{ 'is-waiting': waiting, 'is-idle': !started }">
    <div class="normnet-pb__head">
      <div class="normnet-pb__now">
        <span class="normnet-pb__dot" :class="dotClass" aria-hidden="true" />
        <span class="normnet-pb__now-text">
          <span class="normnet-pb__now-label">{{ stateLabel }}</span>
          <strong class="normnet-pb__now-step">{{ nowLabel }}</strong>
        </span>
      </div>

      <div class="normnet-pb__controls">
        <!-- Pace. The engine finishes a claim in seconds; the run is played at
             reading speed, and this is where that is handed back to the reader. -->
        <template v-if="started">
          <button
            v-if="!finished"
            type="button"
            class="normnet-pb__btn"
            :aria-pressed="paused"
            :title="paused ? 'Verder afspelen' : 'Pauzeer het afspelen'"
            @click="emit('toggle-pause')"
          >
            <span aria-hidden="true">{{ paused ? '▶' : '❚❚' }}</span>
            <span class="normnet-visually-hidden">
              {{ paused ? 'Verder afspelen' : 'Pauzeren' }}
            </span>
          </button>
          <div class="normnet-pb__speeds" role="group" aria-label="Afspeelsnelheid">
            <button
              v-for="s in SPEEDS"
              :key="s.value"
              type="button"
              class="normnet-pb__btn normnet-pb__btn--speed"
              :class="{ 'is-active': speed === s.value }"
              :aria-pressed="speed === s.value"
              :title="s.hint"
              @click="emit('set-speed', s.value)"
            >
              {{ s.label }}
            </button>
          </div>
          <button
            v-if="backlog > 0"
            type="button"
            class="normnet-pb__btn normnet-pb__btn--skip"
            @click="emit('skip')"
          >
            {{ backlog }} in wachtrij — toon direct
          </button>
        </template>

        <!-- A real RVO tertiary button: it opens a different view, so it is
             not styled as a fourth setting of the pace control next to it. -->
        <button
          type="button"
          class="rvo-button rvo-button--tertiary rvo-button--size-xs normnet-pb__graph"
          aria-haspopup="dialog"
          @click="emit('open-graph')"
        >
          {{ expert ? 'Toon graafweergave' : 'Toon het hele proces' }}
        </button>
      </div>
    </div>

    <!-- The rail. Also the progress bar — a second abstract bar next to this
         would be saying the same thing twice, less usefully. -->
    <div class="normnet-pb__railwrap">
      <ol class="normnet-pb__rail">
        <li
          v-for="group in phases"
          :key="group.phase"
          class="normnet-pb__phase"
          :class="`is-${group.state}`"
        >
          <span class="normnet-pb__connector" aria-hidden="true" />
          <span class="normnet-pb__marker">
            <svg v-if="group.state === 'done'" class="normnet-pb__check" viewBox="0 0 16 16">
              <path
                d="M3.5 8.5l3 3 6-7"
                fill="none"
                stroke="currentColor"
                stroke-width="2.4"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span v-else-if="group.state === 'busy'" class="normnet-pb__spinner" aria-hidden="true" />
            <span v-else-if="group.state === 'waiting-human'" aria-hidden="true">!</span>
            <span v-else-if="group.state === 'skipped'" aria-hidden="true">–</span>
            <span v-else aria-hidden="true">{{ group.number }}</span>
          </span>

          <!-- Two steps in one phase are either an AND-split or an exclusive
               choice. Saying which is the difference between a process the
               reader can predict and a list they have to take on faith. -->
          <ul class="normnet-pb__alts">
            <li
              v-for="(step, i) in group.steps"
              :key="step.key"
              class="normnet-pb__alt"
              :class="`is-${step.state}`"
            >
              <span v-if="i > 0" class="normnet-pb__joiner">
                {{ step.kind === 'parallel' ? 'én tegelijk' : 'óf' }}
              </span>
              <!-- The icon sits *inside* the text run, so on a label that
                   wraps it stays pinned to the first word instead of centring
                   itself against two lines and drifting off to the left. -->
              <span class="normnet-pb__label" :title="EXECUTORS[step.executor].explanation">
                <ExecutorIcon
                  :kind="step.executor"
                  class="normnet-pb__exec"
                  :class="`is-key-${step.executor}`"
                  size="0.8rem"
                />{{ ' ' }}<span class="normnet-pb__name">{{ step.label }}</span>
              </span>
            </li>
          </ul>

          <!-- Only where the marker cannot say it already. "Nog niet aan de
               beurt" under eight grey circles and "Afgerond" under a green tick
               are a whole tier of text that adds nothing; the two states a
               reader must not miss keep their words. -->
          <span v-if="LOUD_STATES.has(group.state)" class="normnet-pb__state">
            {{ STATE_TEXT[group.state] }}
          </span>
          <span v-else class="normnet-visually-hidden">{{ STATE_TEXT[group.state] }}</span>
        </li>
      </ol>
    </div>

    <!-- The legend belongs here, under the icons it explains, and nowhere
         else. Keys and names only: three full sentences inside what is really a
         navigation strip was most of what made this bar unreadable. The
         explanation rides along as a tooltip, on the legend and on every step. -->
    <ul class="normnet-pb__legend">
      <li v-for="(meta, kind) in EXECUTORS" :key="kind" :title="meta.explanation">
        <ExecutorIcon :kind="(kind as ExecutorKind)" size="0.8rem" :class="`is-key-${kind}`" />
        {{ meta.label }}
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import ExecutorIcon from './ExecutorIcon.vue'
import { EXECUTORS } from '../labels'
import type { ExecutorKind, NetShape, TransitionActivity } from '../types'
import { useViewMode } from '../useViewMode'
import { STATE_TEXT, useProcessSteps, type StepState } from '../useProcessSteps'

const props = defineProps<{
  net: NetShape
  activity: Record<string, TransitionActivity>
  gated: string[]
  /** a run exists — before that this is a preview of what is going to happen */
  started: boolean
  paused: boolean
  speed: number
  backlog: number
  waiting: boolean
  finished: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-pause'): void
  (e: 'set-speed', value: number): void
  (e: 'skip'): void
  (e: 'open-graph'): void
}>()

/* Three, not four. Slow down, normal, and give up on pacing altogether — 2×
   sat between the last two and earned none of the width it cost. */
const { expert } = useViewMode()

const SPEEDS = [
  { value: 0.5, label: '½×', hint: 'Rustig meelezen' },
  { value: 1, label: '1×', hint: 'Normaal tempo' },
  { value: 0, label: 'direct', hint: 'Geen tempo — toon alles zodra het binnenkomt' },
]

/** States that still need a word under the marker. */
const LOUD_STATES = new Set<StepState>(['busy', 'waiting-human', 'skipped'])

const { phases, doneCount, plannedCount, current } = useProcessSteps(
  toRef(props, 'net'),
  toRef(props, 'activity'),
  toRef(props, 'gated'),
)

const stateLabel = computed(() => {
  if (!props.started) return 'Het proces'
  if (props.waiting) return 'Wacht op u'
  if (props.finished) return 'Afgerond'
  if (props.paused) return 'Gepauzeerd'
  return `Nu bezig · stap ${doneCount.value} van ${plannedCount.value}`
})

const nowLabel = computed(() => {
  if (!props.started) return `Schadeclaim afhandelen — ${plannedCount.value} stappen`
  if (props.finished) return 'Dossier gesloten'
  return current.value?.label ?? 'Run wordt gestart…'
})

const dotClass = computed(() => ({
  'is-idle': !props.started,
  'is-waiting': props.waiting,
  'is-paused': props.paused && !props.waiting,
  'is-done': props.finished,
}))
</script>

<style scoped>
.normnet-pb {
  position: sticky;
  inset-block-start: 0;
  z-index: 20;
  margin-block-end: 1.5rem;
  padding: 0.75rem 1rem 0.6rem;
  background: var(--normnet-color-surface, #fff);
  border: 1px solid var(--normnet-color-border, #e2e8f0);
  border-block-start: 3px solid var(--normnet-color-auto, #007bc7);
  box-shadow: 0 2px 10px rgb(15 23 42 / 0.07);
}
.normnet-pb.is-waiting {
  border-block-start-color: var(--normnet-color-human, #b45309);
}
.normnet-pb.is-idle {
  border-block-start-color: var(--normnet-color-border-strong, #cbd5e1);
}

/* ── Head ─────────────────────────────────────────────────────────────── */
.normnet-pb__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 1rem;
}
.normnet-pb__now {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-inline-size: 0;
}
.normnet-pb__dot {
  inline-size: 0.7rem;
  block-size: 0.7rem;
  border-radius: 50%;
  flex: none;
  background: var(--normnet-color-auto, #007bc7);
  animation: normnet-pulse 1.4s ease-in-out infinite;
}
.normnet-pb__dot.is-idle,
.normnet-pb__dot.is-paused {
  background: var(--normnet-color-text-subtle, #64748b);
  animation: none;
}
.normnet-pb__dot.is-waiting {
  background: var(--normnet-color-human, #b45309);
}
.normnet-pb__dot.is-done {
  background: var(--normnet-color-ok, #39870c);
  animation: none;
}
@keyframes normnet-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.8); }
}
.normnet-pb__now-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-inline-size: 0;
}
.normnet-pb__now-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-pb__now-step {
  font-size: 1rem;
}
.normnet-pb__controls {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.normnet-pb__graph {
  margin-inline-start: 0.5rem;
}
.normnet-pb__speeds {
  display: flex;
}
.normnet-pb__speeds .normnet-pb__btn + .normnet-pb__btn {
  margin-inline-start: -1px;
}
.normnet-pb__btn {
  font: inherit;
  font-size: 0.75rem;
  padding: 0.25rem 0.55rem;
  background: var(--normnet-color-surface, #fff);
  border: 1px solid var(--normnet-color-border-strong, #cbd5e1);
  color: var(--rvo-color-donkerblauw, #01689b);
  cursor: pointer;
  white-space: nowrap;
}
.normnet-pb__btn:hover {
  background: var(--normnet-color-page-bg, #f1f5f9);
}
.normnet-pb__btn--speed.is-active {
  background: var(--rvo-color-donkerblauw, #01689b);
  border-color: var(--rvo-color-donkerblauw, #01689b);
  color: #fff;
}
.normnet-pb__btn--skip {
  border-color: var(--normnet-color-human, #b45309);
  color: var(--normnet-color-human, #b45309);
  font-weight: 700;
}

/* ── Rail ─────────────────────────────────────────────────────────────── */
.normnet-pb__railwrap {
  margin-block: 0.75rem 0.5rem;
  overflow-x: auto;
  padding-block-end: 0.25rem;
}
.normnet-pb__rail {
  display: flex;
  align-items: start;
  list-style: none;
  margin: 0;
  padding: 0;
}
.normnet-pb__phase {
  position: relative;
  flex: 1 1 0;
  min-inline-size: 8rem;
  padding: 0 0.4rem;
  text-align: center;
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-pb__alts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.1rem;
}
.normnet-pb__joiner {
  display: block;
  font-size: 0.625rem;
  font-style: italic;
  text-transform: lowercase;
  color: var(--normnet-color-text-subtle, #64748b);
}
/* The line joins one marker to the previous one and stops at both edges — run
   centre to centre it passes straight through the numeral, which no amount of
   white background reliably hides. R = half the 1.7rem marker. */
.normnet-pb__connector {
  position: absolute;
  inset-block-start: calc(0.85rem - 1px);
  inset-inline: calc(-50% + 0.95rem) calc(50% + 0.95rem);
  block-size: 2px;
  background: var(--normnet-color-border-strong, #cbd5e1);
}
.normnet-pb__phase:first-child .normnet-pb__connector {
  display: none;
}
.normnet-pb__phase.is-done .normnet-pb__connector,
.normnet-pb__phase.is-busy .normnet-pb__connector,
.normnet-pb__phase.is-waiting-human .normnet-pb__connector {
  background: var(--normnet-color-auto, #007bc7);
}
.normnet-pb__marker {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  inline-size: 1.7rem;
  block-size: 1.7rem;
  margin: 0 auto 0.4rem;
  border-radius: 50%;
  border: 2px solid var(--normnet-color-border-strong, #cbd5e1);
  background: var(--normnet-color-surface, #fff);
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1;
}
.normnet-pb__check {
  inline-size: 0.9rem;
  block-size: 0.9rem;
}
.normnet-pb__phase.is-done .normnet-pb__marker {
  border-color: var(--normnet-color-ok, #39870c);
  background: var(--normnet-color-ok, #39870c);
  color: #fff;
}
.normnet-pb__phase.is-busy .normnet-pb__marker {
  border-color: var(--normnet-color-auto, #007bc7);
  color: var(--normnet-color-auto, #007bc7);
}
.normnet-pb__phase.is-waiting-human .normnet-pb__marker {
  border-color: var(--normnet-color-human, #b45309);
  background: var(--normnet-color-human, #b45309);
  color: #fff;
}
.normnet-pb__phase.is-skipped .normnet-pb__marker {
  border-style: dashed;
}
.normnet-pb__spinner {
  inline-size: 0.75rem;
  block-size: 0.75rem;
  border: 2px solid currentColor;
  border-block-start-color: transparent;
  border-radius: 50%;
  animation: normnet-spin 0.8s linear infinite;
}
@keyframes normnet-spin {
  to { transform: rotate(360deg); }
}
.normnet-pb__label {
  display: block;
  font-size: 0.75rem;
  line-height: 1.3;
}
.normnet-pb__exec {
  vertical-align: -0.12em;
  margin-inline-end: 0.15rem;
}
.normnet-pb__alt.is-done .normnet-pb__name,
.normnet-pb__alt.is-busy .normnet-pb__name,
.normnet-pb__alt.is-waiting-human .normnet-pb__name {
  color: var(--rvo-color-zwart, #000);
  font-weight: 700;
}
/* An alternative this case did not take is struck through, not hidden: that it
   was on the table and was not chosen is part of what happened. */
.normnet-pb__alt.is-skipped {
  opacity: 0.55;
}
.normnet-pb__alt.is-skipped .normnet-pb__name {
  text-decoration: line-through;
}
.normnet-pb__state {
  display: block;
  margin-block-start: 0.2rem;
  font-size: 0.6875rem;
  font-style: italic;
}
.normnet-pb__phase.is-waiting-human .normnet-pb__state {
  color: var(--normnet-color-human, #b45309);
  font-weight: 700;
}

/* ── Legend ───────────────────────────────────────────────────────────── */
.normnet-pb__legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.25rem 1.5rem;
  list-style: none;
  margin: 0;
  padding-block-start: 0.5rem;
  border-block-start: 1px solid var(--normnet-color-border, #e2e8f0);
  font-size: 0.6875rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-pb__legend li {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: help;
}
.is-key-deterministic { color: #334155; }
.is-key-llm { color: #5b2d90; }
.is-key-human { color: #8f5c2c; }
/* Same three colours as the badges and the graph, so the mapping only has to
   be learned once — and never carried by colour alone: each icon is distinct
   in shape and every one is named in the legend below. */
.normnet-pb__exec.is-key-deterministic { color: #64748b; }

@media (max-width: 900px) {
  .normnet-pb {
    position: static;
  }
  .normnet-pb__legend-text {
    display: none;
  }
}
</style>
