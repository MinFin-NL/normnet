<template>
  <div class="rvo-theme">
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
              NormNet voert een schadeclaimproces uit als petrinet. Elke stap die
              vuurt verschijnt hieronder: welke agent hem uitvoerde, met welk
              gereedschap, en wat er is vastgelegd.
            </p>
            <p>
              Bij een keuzepunt ziet u <strong>de volledige vraag aan het model</strong>
              — inclusief het normen-blok dat uit de normen is gegenereerd —
              naast het antwoord en de motivatie.
            </p>
            <p>
              Bij een stap die het net markeert als <code>human_in_loop</code> stopt
              het proces en wacht op u. Dat is geen animatie: de achterliggende
              thread staat stil tot u kiest.
            </p>
            <p class="normnet-intro__cta">Kies links een casus en start een run.</p>
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
import HumanGate from './components/HumanGate.vue'
import RunControls from './components/RunControls.vue'
import StatePanel from './components/StatePanel.vue'
import TimelineItem from './components/TimelineItem.vue'
import { api } from './api'
import type { Bootstrap } from './types'
import { useRun } from './useRun'

const boot = ref<Bootstrap | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const run = useRun()

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
.normnet-main {
  padding-block: 1.5rem;
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
  max-block-size: calc(100vh - 2rem);
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
  margin-block-end: 0;
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
</style>
