<template>
  <div class="utrecht-document rvo-theme">
    <a class="normnet-skiplink" href="#main">Naar de hoofdinhoud</a>
    <AppHeader />

    <main
      id="main"
      class="rvo-max-width-layout rvo-max-width-layout--lg rvo-max-width-layout-inline-padding--sm normnet-main"
    >
      <p v-if="loading" class="normnet-loading">Bezig met laden…</p>

      <div v-else-if="loadError" class="rvo-alert rvo-alert--error rvo-alert--padding-md">
        <h2 class="rvo-heading rvo-heading--margin-3">Kan de server niet bereiken</h2>
        <p>{{ loadError }}</p>
        <p class="normnet-loading__hint">
          Draait de API? Start hem met
          <code>uvicorn server.app:app --reload</code> vanuit de projectmap.
        </p>
      </div>

      <template v-else>
        <!-- The process, full width, above everything, in every state of the
             page. It used to be an eleven-item list crammed into the sidebar
             under the start form, with the net itself hidden behind a button —
             the subject of the application was the least prominent thing on
             it. -->
        <ProcessBar
          :net="boot!.nets.to_be"
          :activity="run.activity.value"
          :gated="run.pending.value?.gated ?? []"
          :started="!!run.runId.value"
          :paused="run.paused.value"
          :speed="run.speed.value"
          :backlog="run.backlog.value"
          :waiting="!!run.pending.value"
          :finished="run.status.value === 'done'"
          @toggle-pause="run.setPaused(!run.paused.value)"
          @set-speed="run.setSpeed"
          @skip="run.skipAhead"
          @open-graph="graphOpen = true"
        />

        <ProcessGraph
          v-model:open="graphOpen"
          :net="boot!.nets.to_be"
          :marking="run.marking.value"
          :activity="run.activity.value"
          :gated="run.pending.value?.gated ?? []"
        />

        <div class="normnet-layout">
          <!-- Left: what to run, and what the run has established -->
          <div class="normnet-layout__side">
            <RunControls
              :scenarios="boot!.scenarios"
              :backends="boot!.backends"
              :busy="run.isBusy.value"
              @start="onStart"
            />
            <StatePanel
              v-if="run.runId.value"
              :norms="boot!.norms"
              :facts="run.facts.value"
              :violated-norm-ids="violatedNormIds"
            />
          </div>

          <!-- Right: what actually happened, step by step -->
          <div class="normnet-layout__main">
            <div
              v-if="run.connectionError.value"
              class="rvo-alert rvo-alert--warning rvo-alert--padding-sm normnet-connection"
              role="status"
            >
              {{ run.connectionError.value }}
            </div>

            <HumanGate
              v-if="run.pending.value"
              :pending="run.pending.value"
              :deciding="run.deciding.value"
              @decide="run.decide"
            />

            <section
              v-if="!run.runId.value"
              class="rvo-card rvo-card--outline rvo-card--padding-md normnet-intro"
            >
              <!-- Ranked, not exhaustive. The hook and the call to action come
                   first, because a reader who never starts a run learns
                   nothing; everything that is background reading sits behind a
                   disclosure. The executor legend is not here — it lives under
                   the icons it explains, in the bar above. -->
              <p class="normnet-intro__eyebrow">De demo in het kort</p>
              <h2 class="rvo-heading rvo-heading--margin-3 normnet-intro__title">
                Eén schadeclaim, van melding tot afsluiting.
              </h2>
              <p class="normnet-intro__lead">
                Hierboven staan de stappen die deze claim gaat doorlopen. Zodra u
                start, ziet u ze één voor één gezet worden — en verschijnt
                hieronder per stap wie hem uitvoerde, wat er is besloten en wat
                er in het dossier is vastgelegd.
              </p>
              <p class="normnet-intro__cta">
                <span class="normnet-intro__arrow" aria-hidden="true">←</span>
                Kies links een casus en start een run.
              </p>

              <p class="normnet-intro__gate">
                <strong>Waar een mens moet beslissen, stopt het proces en wacht
                op u.</strong> Dat is geen animatie — er staat werkelijk een
                proces stil tot u kiest.
              </p>
              <p class="normnet-intro__pace">
                De motor is in enkele seconden klaar. Daarom wordt de run op
                leestempo afgespeeld; pauzeren, versnellen of alles ineens tonen
                kan in de balk hierboven.
              </p>

              <details class="rvo-expandable-content normnet-intro__more">
                <summary>Waar kijk ik nou eigenlijk naar?</summary>
                <div class="normnet-intro__more-body">
                  <p>
                    Het proces is vastgelegd als <strong>petrinet</strong>: een
                    stap kan pas beginnen als alles waarop hij wacht er
                    werkelijk is. De beoordeling begint bijvoorbeeld niet
                    voordat zowel de fraude- als de garantiecontrole binnen is —
                    dat is geen instructie aan het model, maar een eigenschap
                    van het net.
                  </p>
                  <p>
                    Daarnaast staan de <strong>normen</strong> apart, als losse
                    regels. Dezelfde regel is de instructie aan het model én de
                    toets achteraf, zodat die twee niet uit elkaar kunnen lopen.
                    Links ziet u ze meelopen; wordt er één geschonden, dan meldt
                    de tijdlijn dat.
                  </p>
                  <p v-if="expert">
                    Bij een keuzepunt ziet u <strong>de volledige vraag aan het
                    model</strong> — inclusief het normen-blok dat uit die
                    normen is gegenereerd — naast het antwoord en de motivatie.
                  </p>
                  <p v-else>
                    Wilt u zien wat er precies aan het model is gevraagd en
                    waarop de audit toetst? Zet <strong>Technische
                    details</strong> aan, rechtsboven.
                  </p>
                  <p class="normnet-intro__credit">
                    Declaratieve laag naar Sileno (2020),
                    <span lang="en">Logic Programming Petri Nets</span>,
                    Universiteit van Amsterdam.
                  </p>
                </div>
              </details>
            </section>

            <!-- Before the first entry lands there is a run but nothing to
                 show yet. Say so, rather than leaving a hole under the bar. -->
            <p
              v-else-if="!run.entries.value.length"
              class="normnet-waiting"
              role="status"
            >
              De run is gestart. De eerste stap verschijnt hier zo…
            </p>

            <!-- aria-live so new steps are announced while the run progresses -->
            <ol
              v-if="run.entries.value.length"
              class="normnet-timeline"
              aria-live="polite"
              aria-relevant="additions"
              :aria-busy="run.isRunning.value"
            >
              <TimelineItem
                v-for="(entry, i) in run.entries.value"
                :key="entry.seq"
                :entry="entry"
                :class="{ 'is-newest': i === run.entries.value.length - 1 }"
                :ref="i === run.entries.value.length - 1 ? setNewest : undefined"
              />
            </ol>

            <p
              v-if="run.runId.value && run.isRunning.value && !run.pending.value && run.entries.value.length"
              class="normnet-status"
              role="status"
            >
              Het proces draait…
            </p>
          </div>
        </div>
      </template>
    </main>

    <AppFooter />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import HumanGate from './components/HumanGate.vue'
import ProcessBar from './components/ProcessBar.vue'
import ProcessGraph from './components/ProcessGraph.vue'
import RunControls from './components/RunControls.vue'
import StatePanel from './components/StatePanel.vue'
import TimelineItem from './components/TimelineItem.vue'
import { api } from './api'
import type { Bootstrap } from './types'
import { useRun } from './useRun'
import { useViewMode } from './useViewMode'

const boot = ref<Bootstrap | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const graphOpen = ref(false)
const run = useRun()
const { expert } = useViewMode()

const violatedNormIds = computed(() => run.violations.value.map((v) => v.normId))

/* Keep the newest card in view — without yanking the page away from someone who
   has deliberately scrolled up to re-read an earlier step. */
let newestEl: HTMLElement | null = null
function setNewest(el: unknown) {
  const node = (el as { $el?: HTMLElement } | null)?.$el ?? (el as HTMLElement | null)
  if (!node || node === newestEl) return
  newestEl = node
  const nearBottom =
    window.innerHeight + window.scrollY >= document.body.offsetHeight - 320
  if (nearBottom) node.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

onMounted(async () => {
  try {
    boot.value = await api.bootstrap()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => run.close())

function onStart(payload: {
  scenario: string
  backend: string
  variant: string
  human_in_the_loop: boolean
  pressure: string
}) {
  run.start(payload).catch((err) => {
    loadError.value = err instanceof Error ? err.message : String(err)
  })
}
</script>

<style scoped>
/* The footer is a fixed overlay strip; reserve its height plus breathing room
   so the last card is never hidden behind it. */
.normnet-main {
  padding-block: var(--rvo-space-md) var(--rvo-space-3xl, 3rem);
}
.normnet-layout {
  display: grid;
  grid-template-columns: minmax(18rem, 22rem) 1fr;
  gap: 1.5rem;
  align-items: start;
}
.normnet-layout__side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-inline-size: 0;
}
.normnet-layout__main {
  min-inline-size: 0;
}
.normnet-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* ── The start card ─────────────────────────────────────────────────────
   Eyebrow, headline, lead, call to action: a reader should be able to stop
   after four lines and still know exactly what to do. */
.normnet-intro {
  background-color: var(--normnet-color-surface, #fff);
  max-inline-size: 80ch;
}
.normnet-intro p {
  margin: 0 0 0.75rem;
}
.normnet-intro__eyebrow {
  margin: 0 0 0.25rem !important;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-intro__title {
  margin-block-start: 0;
  font-size: 1.375rem;
  line-height: 1.25;
}
.normnet-intro__lead {
  font-size: 1rem;
  max-inline-size: 62ch;
}
.normnet-intro__cta {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  margin-block-end: 1.5rem !important;
  padding: 0.5rem 0.75rem;
  background: color-mix(in srgb, var(--normnet-color-auto, #007bc7) 8%, #fff);
  border-inline-start: 3px solid var(--normnet-color-auto, #007bc7);
  font-weight: 700;
}
.normnet-intro__arrow {
  font-size: 1.1em;
  line-height: 1;
}
.normnet-intro__gate {
  padding: 0.5rem 0.75rem;
  background: color-mix(in srgb, var(--normnet-color-human, #b45309) 8%, #fff);
  border-inline-start: 3px solid var(--normnet-color-human, #b45309);
}
.normnet-intro__pace {
  font-size: 0.875rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-intro__more {
  margin-block-start: 1rem;
}
.normnet-intro__more-body {
  padding-block-start: 0.5rem;
  max-inline-size: 70ch;
}
.normnet-intro__credit {
  margin-block-end: 0 !important;
  padding-block-start: 0.75rem;
  border-block-start: 1px solid var(--normnet-color-border, #e2e8f0);
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}

.normnet-connection {
  margin-block-end: 1rem;
}
.normnet-status,
.normnet-waiting {
  color: var(--normnet-color-text-muted, #4b5563);
  font-style: italic;
}
.normnet-loading {
  padding-block: 2rem;
}
.normnet-loading__hint {
  font-size: 0.875rem;
}
code {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-size: 0.8125em;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.1em 0.35em;
  border-radius: 2px;
}

@media (max-width: 900px) {
  .normnet-layout {
    grid-template-columns: 1fr;
  }
}
</style>
