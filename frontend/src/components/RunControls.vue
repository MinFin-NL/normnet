<template>
  <section class="rvo-card rvo-card--outline rvo-card--padding-md normnet-panel" aria-labelledby="run-controls-heading">
    <h2 id="run-controls-heading" class="rvo-heading rvo-heading--margin-3 normnet-panel__title">
      Nieuwe run starten
    </h2>

    <div class="rvo-form-layout">
      <div class="rvo-form-field">
        <label class="normnet-label" for="scenario">Casus</label>
        <div class="rvo-select-wrapper">
          <select id="scenario" v-model="scenario" class="rvo-select--md" :disabled="busy">
            <option v-for="s in scenarios" :key="s.id" :value="s.id">
              {{ s.claim_id }} — {{ s.product }} (€{{ s.amount_eur.toFixed(2) }})
            </option>
          </select>
        </div>
        <p v-if="selected" class="normnet-hint">
          {{ selected.customer }} ·
          {{ selected.in_warranty ? 'binnen garantie' : 'buiten garantie' }} ·
          {{ selected.has_receipt ? 'bon aanwezig' : 'geen bon' }} ·
          {{ selected.prior_claims_12m }} eerdere claim(s)
        </p>
      </div>

      <template v-if="expert">
        <div class="rvo-form-field">
          <label class="normnet-label" for="backend">Wie neemt de besluiten?</label>
          <div class="rvo-select-wrapper">
            <select id="backend" v-model="backend" class="rvo-select--md" :disabled="busy">
              <option v-for="b in backends" :key="b.id" :value="b.id">{{ b.label }}</option>
            </select>
          </div>
          <p class="normnet-hint">{{ backendHint }}</p>
        </div>

        <div class="rvo-form-field">
          <label class="normnet-label" for="pressure">
            Extra bericht van de klant <span class="normnet-label__optional">(optioneel)</span>
          </label>
          <textarea
            id="pressure"
            v-model="pressure"
            class="normnet-textarea"
            rows="3"
            :disabled="busy"
            aria-describedby="pressure-hint"
            placeholder="Bijv. druk uitoefenen, dreigen met publiciteit, of verwijzen naar een collega die het al zou hebben goedgekeurd"
          ></textarea>
          <p id="pressure-hint" class="normnet-hint">
            Wordt vastgelegd als feit, maar geen enkele norm of regel leest het. Zo
            kunt u zien of het besluit er tóch door verandert.
          </p>
        </div>

        <div class="rvo-form-field">
          <div class="normnet-checkbox">
            <input
              id="hitl"
              v-model="humanInTheLoop"
              type="checkbox"
              class="rvo-checkbox"
              :disabled="busy"
              aria-describedby="hitl-hint"
            />
            <label for="hitl" class="normnet-label normnet-label--inline">
              Mens beslist bij stappen die dat vereisen
            </label>
          </div>
          <p id="hitl-hint" class="normnet-hint">
            Bij stappen waar het proces een mens vereist pauzeert de run écht en
            wacht op u. Zet u dit uit, dan blijft het advies van de agent staan en
            is de run niet langer <span lang="en">human-in-the-loop</span>.
          </p>
        </div>
      </template>

      <button
        type="button"
        class="rvo-button rvo-button--primary rvo-button--size-md"
        :disabled="busy"
        @click="emit('start', payload())"
      >
        {{ busy ? 'Bezig…' : 'Start run' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BackendOption, Scenario } from '../types'
import { useViewMode } from '../useViewMode'

const props = defineProps<{
  scenarios: Scenario[]
  backends: BackendOption[]
  busy: boolean
}>()
const emit = defineEmits<{
  start: [payload: {
    scenario: string; backend: string; variant: string
    human_in_the_loop: boolean; pressure: string
  }]
}>()

const { expert } = useViewMode()

const scenario = ref(props.scenarios[0]?.id ?? 'standard')
const backend = ref('mock')
const pressure = ref('')
const humanInTheLoop = ref(true)

const selected = computed(() => props.scenarios.find((s) => s.id === scenario.value) ?? null)
const backendHint = computed(
  () => props.backends.find((b) => b.id === backend.value)?.hint ?? '',
)

/** In the simple view the three technical controls are not on screen, so their
 *  refs must not silently carry a value the user set earlier in expert mode —
 *  send the defaults instead. `mock` is deterministic and needs no Ollama
 *  server, so the demo always runs. `variant` is never exposed at all. */
function payload() {
  return expert.value
    ? {
        scenario: scenario.value,
        backend: backend.value,
        variant: 'to_be',
        human_in_the_loop: humanInTheLoop.value,
        pressure: pressure.value,
      }
    : {
        scenario: scenario.value,
        backend: 'mock',
        variant: 'to_be',
        human_in_the_loop: true,
        pressure: '',
      }
}
</script>

<style scoped>
.normnet-panel {
  background-color: var(--normnet-color-surface, #fff);
}
.normnet-panel__title {
  font-size: 1.125rem;
  margin-block-start: 0;
}
.normnet-label {
  display: block;
  font-weight: 600;
  margin-block-end: 0.25rem;
}
.normnet-label--inline {
  display: inline;
  font-weight: 600;
}
.normnet-label__optional {
  font-weight: 400;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-hint {
  margin: 0.25rem 0 0;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-textarea {
  inline-size: 100%;
  padding: 0.5rem;
  border: 1px solid var(--normnet-color-border-strong, #94a3b8);
  border-radius: 2px;
  font: inherit;
  font-size: 0.875rem;
  resize: vertical;
}
.normnet-checkbox {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}
.rvo-form-field {
  margin-block-end: 1.25rem;
}
code {
  font-size: 0.8125em;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.05em 0.3em;
  border-radius: 2px;
}
</style>
