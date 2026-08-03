<template>
  <!-- Native <dialog>: focus trapping, Escape-to-close and inertness of the page
       behind it come from the platform rather than from hand-written key
       handlers, which is what makes it the accessible choice here. -->
  <dialog
    ref="dialog"
    class="rvo-dialog rvo-dialog--wit rvo-dialog--centered-dialog rvo-dialog--centered-dialog--xl normnet-graph"
    aria-labelledby="graph-heading"
    @close="emit('update:open', false)"
    @click.self="close"
  >
    <div class="normnet-graph__head">
      <div>
        <h2 id="graph-heading" class="rvo-heading rvo-heading--margin-3 normnet-graph__title">
          Het proces als graaf
        </h2>
        <p class="normnet-graph__lead">
          Dezelfde zaak, maar dan het hele model in één beeld: <strong>cirkels</strong>
          zijn toestanden, <strong>blokken</strong> zijn stappen, en een pijl zegt
          welke stap uit welke toestand mag volgen. De zaak zit waar de
          <span class="normnet-graph__token-inline" aria-hidden="true" /> staat.
        </p>
      </div>
      <button
        type="button"
        class="rvo-button rvo-button--tertiary rvo-button--size-sm normnet-graph__close"
        @click="close"
      >
        Sluiten
      </button>
    </div>

    <div class="rvo-dialog__content normnet-graph__content">
      <svg
        class="normnet-graph__svg"
        :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
        role="img"
        :aria-label="summary"
      >
        <defs>
          <marker
            id="normnet-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,1 L9,5 L0,9 z" fill="currentColor" />
          </marker>
        </defs>

        <!-- arcs first, so nodes always sit on top of them -->
        <g class="normnet-graph__arcs">
          <path
            v-for="arc in arcs"
            :key="arc.key"
            :d="arc.d"
            class="normnet-graph__arc"
            :class="{ 'is-live': arc.live }"
            marker-end="url(#normnet-arrow)"
          />
        </g>

        <!-- transitions: the steps -->
        <g>
          <g
            v-for="t in transitionNodes"
            :key="t.id"
            :class="['normnet-graph__t', `is-${t.state}`]"
          >
            <rect
              :x="t.x - T_W / 2"
              :y="t.y - T_H / 2"
              :width="T_W"
              :height="T_H"
              rx="4"
            />
            <text :x="t.x" :y="t.y" text-anchor="middle" dominant-baseline="middle">
              <tspan
                v-for="(line, i) in t.lines"
                :key="i"
                :x="t.x"
                :dy="i === 0 ? (t.lines.length > 1 ? -7 : 0) : 14"
              >{{ line }}</tspan>
            </text>
          </g>
        </g>

        <!-- places: the states -->
        <g>
          <g
            v-for="p in placeNodes"
            :key="p.id"
            :class="['normnet-graph__p', { 'is-marked': p.tokens > 0 }]"
          >
            <circle :cx="p.x" :cy="p.y" :r="P_R" />
            <circle v-if="p.tokens > 0" :cx="p.x" :cy="p.y" :r="7" class="normnet-graph__token" />
            <text
              v-if="p.tokens > 1"
              :x="p.x"
              :y="p.y"
              text-anchor="middle"
              dominant-baseline="middle"
              class="normnet-graph__token-count"
            >{{ p.tokens }}</text>
            <text
              :x="p.x"
              :y="p.y + P_R + 14"
              text-anchor="middle"
              class="normnet-graph__p-label"
            >{{ p.label }}</text>
          </g>
        </g>
      </svg>
    </div>

    <ul class="normnet-graph__legend">
      <li><span class="normnet-graph__key normnet-graph__key--marked" aria-hidden="true" /> Hier staat de zaak nu</li>
      <li><span class="normnet-graph__key normnet-graph__key--done" aria-hidden="true" /> Stap is gedaan</li>
      <li><span class="normnet-graph__key normnet-graph__key--busy" aria-hidden="true" /> Stap draait nu</li>
      <li><span class="normnet-graph__key normnet-graph__key--human" aria-hidden="true" /> Wacht op uw besluit</li>
      <li><span class="normnet-graph__key normnet-graph__key--todo" aria-hidden="true" /> Nog niet geweest</li>
    </ul>
  </dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { netLabel } from '../labels'
import type { NetShape, TransitionActivity } from '../types'

const props = defineProps<{
  open: boolean
  net: NetShape
  marking: Record<string, number>
  activity: Record<string, TransitionActivity>
  gated: string[]
}>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const dialog = ref<HTMLDialogElement | null>(null)

function sync(open: boolean) {
  const el = dialog.value
  if (!el) return
  if (open && !el.open) el.showModal()
  if (!open && el.open) el.close()
}

watch(() => props.open, sync)
// A dialog that mounts already open — a deep link, a test harness — would
// otherwise never be shown: the watcher only fires on a change.
onMounted(() => sync(props.open))

function close() {
  dialog.value?.close()
}

const WIDTH = 720
const HEIGHT = 1370
const P_R = 20
const T_W = 170
const T_H = 38

/** Hand-placed, because a generated layout of a net with a loop, a bypass and
 *  an AND-split is never as readable as one drawn on purpose. Keyed on the ids,
 *  which are stable and shared between the as-is and to-be nets; anything the
 *  map does not know is dropped rather than piled up at the origin, and the
 *  caption below the graph says so. */
const LAYOUT: Record<string, { x: number; y: number }> = {
  p_intake: { x: 400, y: 42 },
  t_register: { x: 400, y: 112 },
  p_registered: { x: 400, y: 182 },
  t_auto_resolve: { x: 175, y: 255 },
  t_request_docs: { x: 470, y: 255 },
  p_await_docs: { x: 470, y: 325 },
  t_docs_rejected: { x: 628, y: 325 },
  t_docs_received: { x: 470, y: 395 },
  p_docs_ok: { x: 470, y: 465 },
  t_split_checks: { x: 470, y: 535 },
  p_fraud_todo: { x: 350, y: 605 },
  p_cover_todo: { x: 590, y: 605 },
  t_fraud_check: { x: 350, y: 675 },
  t_coverage_check: { x: 590, y: 675 },
  p_fraud_done: { x: 350, y: 745 },
  p_cover_done: { x: 590, y: 745 },
  t_assess: { x: 470, y: 820 },
  p_assessed: { x: 470, y: 890 },
  t_approve: { x: 350, y: 960 },
  t_reject: { x: 590, y: 960 },
  p_approved: { x: 350, y: 1030 },
  p_rejected: { x: 590, y: 1030 },
  t_issue_refund: { x: 350, y: 1100 },
  p_paid: { x: 350, y: 1170 },
  t_close_paid: { x: 350, y: 1240 },
  t_close_rejected: { x: 590, y: 1240 },
  p_closed: { x: 470, y: 1315 },
}

/** Two arcs cannot be drawn as a straight line without crossing half the net:
 *  the auto-settle bypass, which skips everything, and the "documents were not
 *  good enough" loop back to intake. Both get an explicit route through a side
 *  channel, which is also how a process drawing would show them. */
const ROUTES: Record<string, string> = {
  't_auto_resolve>p_approved': 'M 175,274 V 320 H 62 V 1030 H 326',
  't_docs_rejected>p_registered': 'M 628,306 V 182 H 424',
}

const placeIds = computed(() => new Set(props.net.places.map((p) => p.id)))

const placeNodes = computed(() =>
  props.net.places
    .filter((p) => LAYOUT[p.id])
    .map((p) => ({
      id: p.id,
      label: netLabel(p.id, p.label),
      tokens: props.marking[p.id] ?? 0,
      ...LAYOUT[p.id],
    })),
)

const transitionNodes = computed(() =>
  props.net.transitions
    .filter((t) => LAYOUT[t.id])
    .map((t) => {
      const info = props.activity[t.id]
      const state = info?.fired
        ? 'done'
        : props.gated.includes(t.id)
          ? 'human'
          : info?.busy
            ? 'busy'
            : 'todo'
      return { id: t.id, state, lines: wrap(netLabel(t.id, t.label)), ...LAYOUT[t.id] }
    }),
)

/** Every input and output arc of every transition, clipped to the node edges so
 *  the arrowhead lands on the circle or the box rather than in its middle. */
const arcs = computed(() => {
  const out: { key: string; d: string; live: boolean }[] = []
  for (const t of props.net.transitions) {
    if (!LAYOUT[t.id]) continue
    const fired = !!props.activity[t.id]?.fired
    for (const place of t.inputs) {
      if (!LAYOUT[place] || !placeIds.value.has(place)) continue
      out.push({
        key: `${place}>${t.id}`,
        d: ROUTES[`${place}>${t.id}`] ?? edge(LAYOUT[place], LAYOUT[t.id], true),
        live: fired,
      })
    }
    for (const place of t.outputs) {
      if (!LAYOUT[place] || !placeIds.value.has(place)) continue
      out.push({
        key: `${t.id}>${place}`,
        d: ROUTES[`${t.id}>${place}`] ?? edge(LAYOUT[t.id], LAYOUT[place], false),
        live: fired,
      })
    }
  }
  return out
})

/** A straight line from the edge of the source node to the edge of the target,
 *  `toTransition` telling us which end is the box and which the circle. */
function edge(
  from: { x: number; y: number },
  to: { x: number; y: number },
  toTransition: boolean,
): string {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  const start = toTransition ? circleEdge(ux, uy) : boxEdge(ux, uy)
  const end = toTransition ? boxEdge(-ux, -uy) : circleEdge(-ux, -uy)
  return `M ${from.x + start.x},${from.y + start.y} L ${to.x + end.x},${to.y + end.y}`
}

function circleEdge(ux: number, uy: number) {
  return { x: ux * (P_R + 3), y: uy * (P_R + 3) }
}

/** Where a ray leaves the transition box — the box is wide and flat, so the
 *  side it exits depends on the angle, not on the distance. */
function boxEdge(ux: number, uy: number) {
  const sx = ux === 0 ? Infinity : (T_W / 2 + 3) / Math.abs(ux)
  const sy = uy === 0 ? Infinity : (T_H / 2 + 3) / Math.abs(uy)
  const s = Math.min(sx, sy)
  return { x: ux * s, y: uy * s }
}

/** Two lines at most; the labels are Dutch sentences and a box is 152 wide. */
function wrap(label: string): string[] {
  const words = label.split(' ')
  const lines: string[] = ['']
  for (const word of words) {
    const line = lines[lines.length - 1]
    if (!line) lines[lines.length - 1] = word
    else if ((line + ' ' + word).length <= 26) lines[lines.length - 1] = `${line} ${word}`
    else if (lines.length < 2) lines.push(word)
    else {
      lines[1] = `${lines[1].slice(0, 23)}…`
      break
    }
  }
  return lines
}

const summary = computed(() => {
  const here = placeNodes.value.filter((p) => p.tokens > 0).map((p) => p.label)
  return here.length
    ? `Procesgraaf. De zaak staat nu bij: ${here.join(', ')}.`
    : 'Procesgraaf van het claimproces.'
})
</script>

<style scoped>
/* `.rvo-dialog` sets `display: flex`, which overrides the user-agent rule that
   hides a closed <dialog> — without this the graph is permanently on screen. */
.normnet-graph:not([open]) {
  display: none;
}
.normnet-graph {
  --rvo-dialog-centered-dialog-max-height: 92vh;
  inline-size: min(52rem, 96vw);
  max-block-size: 92vh;
  border-radius: 4px;
  box-shadow: 0 12px 40px rgb(0 0 0 / 0.25);
}
.normnet-graph::backdrop {
  background: rgb(18 22 26 / 0.55);
}
.normnet-graph__head {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  inline-size: 100%;
}
.normnet-graph__title {
  margin-block-start: 0;
  font-size: 1.25rem;
}
.normnet-graph__lead {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  color: var(--normnet-color-text-muted, #4b5563);
  max-inline-size: 70ch;
}
.normnet-graph__token-inline {
  display: inline-block;
  inline-size: 0.7rem;
  block-size: 0.7rem;
  border-radius: 50%;
  background: var(--normnet-color-ok, #39870c);
  vertical-align: -0.05em;
}
.normnet-graph__close {
  margin-inline-start: auto;
  flex: none;
}
.normnet-graph__content {
  border: 1px solid var(--normnet-color-border, #e2e8f0);
  border-radius: 4px;
  background: var(--normnet-color-surface, #fff);
  padding: 0.5rem;
}
.normnet-graph__svg {
  inline-size: 100%;
  block-size: auto;
  font-family: inherit;
}

/* ── arcs ──────────────────────────────────────────────────────────────── */
.normnet-graph__arcs {
  color: var(--normnet-color-border-strong, #cbd5e1);
}
.normnet-graph__arc {
  fill: none;
  stroke: var(--normnet-color-border-strong, #cbd5e1);
  stroke-width: 1.5;
}
.normnet-graph__arc.is-live {
  stroke: var(--normnet-color-ok, #39870c);
  stroke-width: 2;
  color: var(--normnet-color-ok, #39870c);
}

/* ── transitions ───────────────────────────────────────────────────────── */
.normnet-graph__t rect {
  fill: var(--rvo-color-wit, #fff);
  stroke: var(--normnet-color-border-strong, #cbd5e1);
  stroke-width: 1.5;
}
.normnet-graph__t text {
  font-size: 11px;
  fill: var(--normnet-color-text-subtle, #64748b);
}
.normnet-graph__t.is-done rect {
  fill: #eef7e7;
  stroke: var(--normnet-color-ok, #39870c);
}
.normnet-graph__t.is-done text {
  fill: var(--rvo-color-zwart, #12161a);
}
.normnet-graph__t.is-busy rect {
  fill: #e6f2fa;
  stroke: var(--rvo-color-hemelblauw, #007bc7);
  stroke-width: 2.5;
}
.normnet-graph__t.is-busy text {
  fill: var(--rvo-color-zwart, #12161a);
  font-weight: 700;
}
.normnet-graph__t.is-human rect {
  fill: #fff3d6;
  stroke: var(--normnet-color-human, #ffb612);
  stroke-width: 2.5;
}
.normnet-graph__t.is-human text {
  fill: var(--rvo-color-zwart, #12161a);
  font-weight: 700;
}

/* ── places ────────────────────────────────────────────────────────────── */
.normnet-graph__p circle {
  fill: var(--rvo-color-wit, #fff);
  stroke: var(--normnet-color-border-strong, #cbd5e1);
  stroke-width: 1.5;
}
.normnet-graph__p.is-marked circle {
  stroke: var(--normnet-color-ok, #39870c);
  stroke-width: 2.5;
}
/* Specific enough to beat `.normnet-graph__p circle`, which fills every circle
   in a place group white — including, otherwise, the token. */
.normnet-graph__p circle.normnet-graph__token {
  fill: var(--normnet-color-ok, #39870c);
  stroke: none;
}
.normnet-graph__token-count {
  font-size: 9px;
  font-weight: 700;
  fill: var(--rvo-color-wit, #fff);
}
.normnet-graph__p-label {
  font-size: 11px;
  fill: var(--normnet-color-text-muted, #4b5563);
  /* An arc runs straight through the label below a place; the halo keeps the
     text readable without moving it off-centre. */
  paint-order: stroke;
  stroke: var(--rvo-color-wit, #fff);
  stroke-width: 3px;
  stroke-linejoin: round;
}
.normnet-graph__p.is-marked .normnet-graph__p-label {
  fill: var(--rvo-color-zwart, #12161a);
  font-weight: 700;
}

/* ── legend ────────────────────────────────────────────────────────────── */
.normnet-graph__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1.1rem;
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  inline-size: 100%;
  font-size: 0.75rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-graph__legend li {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.normnet-graph__key {
  inline-size: 0.85rem;
  block-size: 0.85rem;
  border-radius: 3px;
  border: 2px solid var(--normnet-color-border-strong, #cbd5e1);
  background: var(--rvo-color-wit, #fff);
  flex: none;
}
.normnet-graph__key--marked {
  border-radius: 50%;
  border-color: var(--normnet-color-ok, #39870c);
  background: var(--normnet-color-ok, #39870c);
}
.normnet-graph__key--done {
  border-color: var(--normnet-color-ok, #39870c);
  background: #eef7e7;
}
.normnet-graph__key--busy {
  border-color: var(--rvo-color-hemelblauw, #007bc7);
  background: #e6f2fa;
}
.normnet-graph__key--human {
  border-color: var(--normnet-color-human, #ffb612);
  background: #fff3d6;
}
</style>
