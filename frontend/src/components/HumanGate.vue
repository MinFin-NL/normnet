<template>
  <!-- role="alert" + aria-live so a screen-reader user is told the process has
       stopped and is waiting for them, rather than discovering it by scrolling. -->
  <section
    class="rvo-alert rvo-alert--warning rvo-alert--padding-md normnet-gate"
    role="alert"
    aria-live="assertive"
    aria-labelledby="gate-heading"
  >
    <h2 id="gate-heading" class="rvo-heading rvo-heading--margin-3 normnet-gate__title">
      Het proces wacht op u
    </h2>

    <p v-if="expert" class="normnet-gate__lead">
      Stap <strong>{{ pending.decision_id }}</strong> in ronde
      <strong>{{ pending.round }}</strong> is in het net gemarkeerd als
      <code>human_in_loop</code>. De agent heeft het werk gedaan en een advies
      opgesteld; het besluit is aan u. Zolang u niets kiest, staat het proces
      daadwerkelijk stil.
    </p>
    <p v-else class="normnet-gate__lead">
      <strong>{{ stepLabel }}</strong> Hier beslist een mens. De agent heeft het
      werk gedaan en een advies opgesteld; het besluit is aan u. Zolang u niets
      kiest, staat het proces daadwerkelijk stil.
    </p>

    <div class="normnet-gate__recommendation">
      <p class="normnet-gate__reco-label">Advies van de agent</p>
      <p class="normnet-gate__reco-choice">
        {{ optionLabel(pending.recommendation) }}
        <span class="rvo-tag rvo-tag--info rvo-tag--pill normnet-gate__confidence">
          zekerheid {{ Math.round((pending.confidence ?? 0) * 100) }}%
        </span>
      </p>
      <p class="normnet-gate__reco-why">“{{ pending.rationale }}”</p>
    </div>

    <div class="normnet-gate__actions">
      <button
        v-for="option in pending.options"
        :key="option"
        type="button"
        class="rvo-button rvo-button--size-md"
        :class="option === pending.recommendation ? 'rvo-button--primary' : 'rvo-button--secondary'"
        :disabled="deciding"
        @click="emit('decide', option)"
      >
        {{ optionLabel(option) }}
        <span v-if="option === pending.recommendation" class="normnet-visually-hidden">
          (dit is het advies van de agent)
        </span>
      </button>
    </div>

    <p class="normnet-gate__note">
      Kiest u iets anders dan het advies, dan wordt dat vastgelegd als een
      <em>override</em>. De normen worden daarna net zo hard op uw besluit
      gecontroleerd als op dat van de agent — keurt u een claim buiten garantie
      goed, dan is dat net zo goed een schending.
    </p>

    <details class="rvo-expandable-content normnet-gate__details">
      <summary>Waar baseert de agent zich op?</summary>
      <dl class="normnet-facts" :class="{ 'normnet-facts--raw': expert }">
        <template v-for="[key, value] in factEntries" :key="key">
          <dt>{{ expert ? key : factLabel(key) }}</dt>
          <dd>{{ factValue(value) }}</dd>
        </template>
      </dl>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { decisionLabel, factLabel, factValue, isKnownFact, netLabel } from '../labels'
import type { PendingDecision } from '../types'
import { useViewMode } from '../useViewMode'

const props = defineProps<{ pending: PendingDecision; deciding: boolean }>()
const emit = defineEmits<{ decide: [choice: string] }>()

const { expert } = useViewMode()

const stepLabel = computed(() => decisionLabel(props.pending.decision_id))

/** The options are transition ids and `pending.labels` carries the net's English
 *  label for each; both go through the Dutch map. */
function optionLabel(id: string): string {
  return netLabel(id, props.pending.labels[id] ?? id)
}

const factEntries = computed(() => {
  const entries = Object.entries(props.pending.facts)
  return expert.value ? entries : entries.filter(([key]) => isKnownFact(key))
})
</script>

<style scoped>
.normnet-gate {
  margin-block-end: 1.5rem;
}
.normnet-gate__title {
  margin-block-start: 0;
  font-size: 1.125rem;
}
.normnet-gate__lead {
  margin-block: 0 1rem;
  max-inline-size: 80ch;
}
.normnet-gate__recommendation {
  background: var(--normnet-color-surface, #fff);
  border: 1px solid var(--normnet-color-border-strong, #94a3b8);
  border-radius: 3px;
  padding: 0.75rem 1rem;
  margin-block-end: 1rem;
}
.normnet-gate__reco-label {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-gate__reco-choice {
  margin: 0.25rem 0;
  font-size: 1.0625rem;
  font-weight: 700;
}
.normnet-gate__confidence {
  margin-inline-start: 0.5rem;
  vertical-align: middle;
}
.normnet-gate__reco-why {
  margin: 0;
  font-style: italic;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-gate__actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-block-end: 1rem;
}
.normnet-gate__note {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  max-inline-size: 80ch;
}
.normnet-gate__details {
  font-size: 0.875rem;
}
.normnet-facts {
  display: grid;
  grid-template-columns: minmax(10rem, max-content) 1fr;
  gap: 0.15rem 1rem;
  margin: 0.5rem 0 0;
  font-size: 0.8125rem;
}
.normnet-facts dt {
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-facts--raw dt {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
}
.normnet-facts dd {
  margin: 0;
}
code {
  font-size: 0.8125em;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.05em 0.3em;
  border-radius: 2px;
}
</style>
