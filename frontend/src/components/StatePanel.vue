<template>
  <div class="normnet-side">
    <!-- Where the tokens are right now -->
    <section
      class="rvo-card rvo-card--outline rvo-card--padding-md normnet-panel"
      aria-labelledby="marking-heading"
    >
      <h2 id="marking-heading" class="rvo-heading rvo-heading--margin-3 normnet-panel__title">
        Waar staat de zaak nu?
      </h2>
      <p v-if="expert" class="normnet-panel__intro">
        De <em>marking</em>: welke plaatsen een token bevatten. Dit ís de toestand
        van het proces — er is geen aparte statusvariabele.
      </p>
      <p v-else class="normnet-panel__intro">
        De stappen die het proces nu heeft bereikt.
      </p>
      <ul class="normnet-places">
        <li
          v-for="place in net.places"
          :key="place.id"
          class="normnet-place"
          :class="{ 'normnet-place--marked': (marking[place.id] ?? 0) > 0 }"
        >
          <span
            class="rvo-status-indicator"
            :class="(marking[place.id] ?? 0) > 0 ? 'rvo-status-indicator--groen' : 'rvo-status-indicator--grijs'"
            aria-hidden="true"
          />
          <span class="normnet-place__label">{{ netLabel(place.id, place.label) }}</span>
          <span v-if="(marking[place.id] ?? 0) > 0" class="normnet-place__state">
            {{ expert ? 'token aanwezig' : 'hier' }}
          </span>
          <span v-else class="normnet-visually-hidden">geen token</span>
        </li>
      </ul>
    </section>

    <!-- Norm status -->
    <section
      class="rvo-card rvo-card--outline rvo-card--padding-md normnet-panel"
      aria-labelledby="norms-heading"
    >
      <h2 id="norms-heading" class="rvo-heading rvo-heading--margin-3 normnet-panel__title">
        Normen
      </h2>
      <p v-if="expert" class="normnet-panel__intro">
        Eén object per norm: dit is tegelijk de instructie aan de agent, de
        controle tijdens de run en het criterium van de audit.
      </p>
      <p v-else class="normnet-panel__intro">
        De regels waaraan dit proces zich moet houden. Ze gelden voor de agent én
        voor u.
      </p>
      <ul class="normnet-norms">
        <li v-for="norm in norms" :key="norm.id" class="normnet-norm">
          <div class="normnet-norm__head">
            <span
              class="rvo-tag rvo-tag--pill"
              :class="violatedIds.has(norm.id) ? 'rvo-tag--error' : 'rvo-tag--success'"
            >
              {{ expert ? norm.id : (violatedIds.has(norm.id) ? 'geschonden' : 'in orde') }}
            </span>
            <span class="normnet-norm__kind">
              {{ norm.kind === 'obligation' ? 'verplichting' : 'verbod' }}
            </span>
            <span
              v-if="expert"
              class="normnet-norm__status"
              :class="violatedIds.has(norm.id) ? 'normnet-norm__status--bad' : ''"
            >
              {{ violatedIds.has(norm.id) ? 'geschonden' : 'niet geschonden' }}
            </span>
          </div>
          <p class="normnet-norm__guidance">{{ norm.guidance }}</p>
          <code v-if="expert" class="normnet-norm__body">:- {{ norm.body.join(', ') }}.</code>
        </li>
      </ul>
    </section>

    <!-- Facts learned so far -->
    <section
      v-if="factEntries.length"
      class="rvo-card rvo-card--outline rvo-card--padding-md normnet-panel"
      aria-labelledby="facts-heading"
    >
      <h2 id="facts-heading" class="rvo-heading rvo-heading--margin-3 normnet-panel__title">
        {{ expert ? 'Vastgelegde feiten' : 'Wat er in het dossier staat' }}
      </h2>
      <dl class="normnet-factlist" :class="{ 'normnet-factlist--raw': expert }">
        <template v-for="[key, value] in factEntries" :key="key">
          <dt>{{ expert ? key : factLabel(key) }}</dt>
          <dd>{{ factValue(value) }}</dd>
        </template>
      </dl>
      <p
        v-if="expert && 'customer_pressure' in facts && facts.customer_pressure"
        class="normnet-panel__note"
      >
        <strong>Let op:</strong> <code>customer_pressure</code> staat wél in het
        dossier, maar geen enkele regel of norm leest het. Verandert de uitkomst
        tóch, dan is dat precies wat de audit aantoont.
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { factLabel, factValue, isKnownFact, netLabel } from '../labels'
import type { NetShape, NormInfo } from '../types'
import { useViewMode } from '../useViewMode'

const props = defineProps<{
  net: NetShape
  marking: Record<string, number>
  norms: NormInfo[]
  facts: Record<string, unknown>
  violatedNormIds: string[]
}>()

const { expert } = useViewMode()

const violatedIds = computed(() => new Set(props.violatedNormIds))

/** In the simple view, only facts we have a Dutch label for. A new key added to
 *  the engine then stays invisible here rather than leaking `some_new_key` into
 *  a page meant for a non-technical reader. */
const factEntries = computed(() => {
  const entries = Object.entries(props.facts)
  return expert.value ? entries : entries.filter(([key]) => isKnownFact(key))
})
</script>

<style scoped>
.normnet-side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.normnet-panel {
  background-color: var(--normnet-color-surface, #fff);
}
.normnet-panel__title {
  margin-block-start: 0;
  font-size: 1.125rem;
}
.normnet-panel__intro {
  margin: 0 0 0.75rem;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-panel__note {
  margin: 0.75rem 0 0;
  font-size: 0.8125rem;
}
.normnet-places {
  list-style: none;
  margin: 0;
  padding: 0;
}
.normnet-place {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-block: 0.25rem;
  font-size: 0.875rem;
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-place--marked {
  color: inherit;
  font-weight: 700;
}
.normnet-place__state {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-ok, #39870c);
  font-weight: 400;
}
.rvo-status-indicator--grijs {
  background-color: var(--normnet-color-border-strong, #cbd5e1);
  border-radius: 50%;
  inline-size: 0.6rem;
  block-size: 0.6rem;
  flex: none;
}
.normnet-norms {
  list-style: none;
  margin: 0;
  padding: 0;
}
.normnet-norm {
  padding-block: 0.6rem;
  border-block-start: 1px solid var(--normnet-color-border, #e2e8f0);
}
.normnet-norm:first-child {
  border-block-start: 0;
  padding-block-start: 0;
}
.normnet-norm__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-block-end: 0.25rem;
}
.normnet-norm__kind,
.normnet-norm__status {
  font-size: 0.75rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-norm__status--bad {
  color: var(--normnet-color-violation, #d52b1e);
  font-weight: 700;
}
.normnet-norm__guidance {
  margin: 0 0 0.35rem;
  font-size: 0.8125rem;
}
.normnet-norm__body,
code {
  display: inline-block;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-size: 0.75rem;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.15em 0.4em;
  border-radius: 2px;
  word-break: break-word;
}
.normnet-factlist {
  display: grid;
  grid-template-columns: minmax(8rem, max-content) 1fr;
  gap: 0.15rem 0.75rem;
  margin: 0;
  font-size: 0.8125rem;
}
.normnet-factlist dt {
  color: var(--normnet-color-text-muted, #4b5563);
  word-break: break-word;
}
/* Raw engine keys read as code; the Dutch labels do not. */
.normnet-factlist--raw dt {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
}
.normnet-factlist dd {
  margin: 0;
  word-break: break-word;
}
</style>
