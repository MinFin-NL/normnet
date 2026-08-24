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

      <div v-else class="normnet-layout">
        <!-- Left: controls + live state -->
        <div class="normnet-layout__side">
          <RunControls
            :scenarios="boot!.scenarios"
            :backends="boot!.backends"
            :busy="run.isBusy.value"
            @start="onStart"
          />
          <StatePanel
            v-if="run.runId.value"
            :net="boot!.nets.to_be"
            :marking="run.marking.value"
            :activity="run.activity.value"
            :gated="run.pending.value?.gated ?? []"
            :norms="boot!.norms"
            :facts="run.facts.value"
            :violated-norm-ids="violatedNormIds"
          />
        </div>

        <!-- Right: the timeline -->
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

          <section v-if="!run.runId.value" class="rvo-card rvo-card--outline rvo-card--padding-md normnet-intro">
            <h2 class="rvo-heading rvo-heading--margin-3 normnet-intro__title">
              Wat ziet u hier?
            </h2>
            <p>
              NormNet handelt een schadeclaim af. Elke stap die het proces zet
              verschijnt hieronder: wie hem uitvoerde, wat er is besloten en wat
              er in het dossier is vastgelegd.
            </p>

            <!-- The distinction the whole inspector exists to make: not every
                 step is a model call, and the reader should be able to tell
                 which is which at a glance, on every step, everywhere. -->
            <h3 class="normnet-intro__subtitle">Wie voert een stap uit?</h3>
            <ul class="normnet-intro__executors">
              <li v-for="(meta, kind) in EXECUTORS" :key="kind">
                <ExecutorBadge :kind="(kind as ExecutorKind)" />
                <span>{{ meta.explanation }}</span>
              </li>
            </ul>
            <p class="normnet-intro__executors-note">
              Deze aanduiding staat bij élke stap — in de tijdlijn, in het
              overzicht links en in de graafweergave.
            </p>
            <p>
              Bij een stap waar een mens moet beslissen stopt het proces en wacht
              op u. Dat is geen animatie — er staat werkelijk een proces stil tot
              u kiest.
            </p>
            <p v-if="expert">
              Bij een keuzepunt ziet u <strong>de volledige vraag aan het model</strong>
              — inclusief het normen-blok dat uit de normen is gegenereerd —
              naast het antwoord en de motivatie.
            </p>
            <p v-else class="normnet-intro__more">
              Wilt u zien wat er precies aan het model is gevraagd en waarop de
              audit toetst? Zet <strong>Technische details</strong> aan, rechtsboven.
            </p>
            <p class="normnet-intro__cta">Kies links een casus en start een run.</p>
            <p class="normnet-intro__credit">
              Declaratieve laag naar Sileno (2020),
              <span lang="en">Logic Programming Petri Nets</span>, Universiteit van
              Amsterdam.
            </p>
          </section>

          <!-- aria-live so new steps are announced while the run progresses -->
          <ol
            v-if="run.entries.value.length"
            class="normnet-timeline"
            aria-live="polite"
            aria-relevant="additions"
            :aria-busy="run.isRunning.value"
          >
            <TimelineItem
              v-for="entry in run.entries.value"
              :key="entry.seq"
              :entry="entry"
            />
          </ol>

          <p
            v-if="run.runId.value && run.isRunning.value && !run.pending.value"
            class="normnet-status"
            role="status"
          >
            Het proces draait…
          </p>
        </div>
      </div>
    </main>

    <AppFooter />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import ExecutorBadge from './components/ExecutorBadge.vue'
import HumanGate from './components/HumanGate.vue'
import RunControls from './components/RunControls.vue'
import StatePanel from './components/StatePanel.vue'
import TimelineItem from './components/TimelineItem.vue'
import { api } from './api'
import { EXECUTORS } from './labels'
import type { Bootstrap, ExecutorKind } from './types'
import { useRun } from './useRun'
import { useViewMode } from './useViewMode'

const boot = ref<Bootstrap | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const run = useRun()
const { expert } = useViewMode()

const violatedNormIds = computed(() => run.violations.value.map((v) => v.normId))

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
  grid-template-columns: minmax(18rem, 24rem) 1fr;
  gap: 1.5rem;
  align-items: start;
}
.normnet-layout__side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  /* Leave room for the fixed footer strip, or the bottom of this column's own
     scroll area sits behind it and can never be reached. */
  max-block-size: calc(100vh - 2rem - 3rem);
  overflow-y: auto;
}
.normnet-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.normnet-intro {
  background-color: var(--normnet-color-surface, #fff);
  max-inline-size: 80ch;
}
.normnet-intro__title {
  margin-block-start: 0;
  font-size: 1.125rem;
}
.normnet-intro p {
  margin: 0 0 0.75rem;
}
.normnet-intro__cta {
  font-weight: 700;
}
.normnet-intro__more {
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-intro__credit {
  margin-block-end: 0;
  padding-block-start: 0.75rem;
  border-block-start: 1px solid var(--normnet-color-border, #e2e8f0);
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-connection {
  margin-block-end: 1rem;
}
.normnet-status {
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
  .normnet-layout__side {
    position: static;
    max-block-size: none;
    overflow: visible;
  }
}
.normnet-intro__subtitle {
  margin: 0 0 0.5rem;
  font-size: 0.9375rem;
  font-weight: 700;
}
.normnet-intro__executors {
  list-style: none;
  margin: 0 0 0.5rem;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}
.normnet-intro__executors li {
  display: grid;
  grid-template-columns: 10rem 1fr;
  gap: 0.6rem;
  align-items: baseline;
  font-size: 0.875rem;
}
.normnet-intro__executors-note {
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}

@media (max-width: 560px) {
  .normnet-intro__executors li {
    grid-template-columns: 1fr;
  }
}
</style>
