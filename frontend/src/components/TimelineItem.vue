<template>
  <!-- ── A model decision ──────────────────────────────────────────────── -->
  <li v-if="entry.type === 'decision'" class="normnet-item">
    <div class="normnet-item__marker normnet-item__marker--decision" aria-hidden="true">?</div>
    <article class="rvo-card rvo-card--outline rvo-card--padding-md normnet-card">
      <header class="normnet-card__head">
        <h3 class="normnet-card__title">
          Besluit: {{ expert ? entry.decisionId : decisionLabel(entry.decisionId) }}
          <span class="normnet-card__round">ronde {{ entry.round }}</span>
        </h3>
        <span class="normnet-card__who">
          <ExecutorBadge kind="llm" />
          <code v-if="expert" class="normnet-card__backend">{{ entry.backend }}</code>
        </span>
      </header>
      <p class="normnet-card__who-line">
        Op dit punt stond meer dan één vervolgstap open. Een <strong>taalmodel</strong>
        heeft gekozen<template v-if="entry.human || entry.awaitingHuman">, maar een
        <strong>mens</strong> beslist</template>.
      </p>

      <p v-if="!entry.choice" class="normnet-card__pending">
        Het model is aan het nadenken…
      </p>

      <template v-else>
        <p class="normnet-card__answer">
          <span class="normnet-card__answer-label">Gekozen</span>
          <strong>{{ netLabel(entry.choice ?? '', entry.choiceLabel) }}</strong>
          <span class="rvo-tag rvo-tag--pill normnet-card__meta">
            zekerheid {{ Math.round(entry.confidence * 100) }}%
          </span>
          <span v-if="expert" class="rvo-tag rvo-tag--pill normnet-card__meta">
            {{ entry.elapsedMs }} ms
          </span>
        </p>
        <blockquote class="normnet-card__rationale">{{ entry.rationale }}</blockquote>

        <p v-if="entry.human" class="normnet-card__human">
          <template v-if="entry.human.overrode">
            <span class="rvo-tag rvo-tag--warning rvo-tag--pill">Door mens gewijzigd</span>
            Een mens koos <strong>{{ netLabel(entry.human.choice, entry.human.label) }}</strong> in plaats van het
            advies van de agent.
          </template>
          <template v-else>
            <span class="rvo-tag rvo-tag--success rvo-tag--pill">Door mens bevestigd</span>
            Een mens heeft <strong>{{ netLabel(entry.human.choice, entry.human.label) }}</strong> vastgesteld.
          </template>
        </p>
      </template>

      <details v-if="expert" class="rvo-expandable-content normnet-card__prompt">
        <summary>Wat is er precies aan het model gevraagd?</summary>
        <div class="normnet-prompt">
          <h4 class="normnet-prompt__heading">Systeeminstructie</h4>
          <pre class="normnet-prompt__text">{{ entry.systemPrompt }}</pre>
          <p class="normnet-prompt__note">
            Het normen-blok hierboven is <strong>gegenereerd</strong> uit dezelfde
            normen waarop de audit toetst — niet apart ingetypt. Daarom kunnen ze
            niet uit elkaar gaan lopen.
          </p>
          <h4 class="normnet-prompt__heading">Casus en feiten</h4>
          <pre class="normnet-prompt__text">{{ entry.userPrompt }}</pre>
          <h4 class="normnet-prompt__heading">Toegestane opties</h4>
          <p class="normnet-prompt__options">
            <code v-for="o in entry.options" :key="o">{{ o }}</code>
          </p>
        </div>
      </details>
    </article>
  </li>

  <!-- ── A round: one or more transitions firing ───────────────────────── -->
  <li v-else-if="entry.type === 'step'" class="normnet-item">
    <div class="normnet-item__marker" aria-hidden="true">{{ entry.round }}</div>
    <article class="rvo-card rvo-card--outline rvo-card--padding-md normnet-card">
      <header class="normnet-card__head">
        <h3 class="normnet-card__title">
          Ronde {{ entry.round }}
          <span v-if="entry.concurrent" class="rvo-tag rvo-tag--info rvo-tag--pill">
            {{ entry.transitions.length }} stappen tegelijk
          </span>
        </h3>
      </header>
      <p v-if="entry.concurrent && expert" class="normnet-card__concurrent-note">
        Deze stappen draaien parallel omdat het net zegt dat de tokens er voor
        beide zijn — niet omdat iemand eraan dacht ze parallel te zetten.
      </p>
      <p v-else-if="entry.concurrent" class="normnet-card__concurrent-note">
        Deze stappen draaien tegelijk omdat de zaak op beide plekken tegelijk
        ligt — niet omdat iemand eraan dacht ze parallel te zetten.
      </p>

      <div v-for="t in entry.transitions" :key="t.id" class="normnet-transition">
        <div class="normnet-transition__head">
          <span class="normnet-transition__label">{{ netLabel(t.id, t.label) }}</span>
          <code v-if="expert" class="normnet-transition__id">{{ t.id }}</code>
          <ExecutorBadge :kind="t.executor" :llm-advises="t.llmAdvises" />
        </div>
        <p class="normnet-transition__actor">
          <span class="normnet-visually-hidden">Uitgevoerd door</span>
          {{ actorLabel(t.actor) }}
          <span class="normnet-transition__how">· {{ executorMeta(t.executor).explanation }}</span>
          <template v-if="expert && t.tools.length">
            · gereedschap:
            <code v-for="tool in t.tools" :key="tool">{{ tool }}</code>
          </template>
          · {{ formatHours(t.hours) }}
        </p>
        <p v-if="t.note" class="normnet-transition__note">{{ t.note }}</p>
        <p v-if="learnedFacts(t.factsLearned).length" class="normnet-transition__facts">
          <span class="normnet-transition__facts-label">Vastgelegd:</span>
          <span
            v-for="[k, v] in learnedFacts(t.factsLearned)"
            :key="k"
            class="normnet-fact"
            :class="{ 'normnet-fact--raw': expert }"
          >
            {{ expert ? k : factLabel(k) }}: {{ factValue(v) }}
          </span>
        </p>
      </div>
    </article>
  </li>

  <!-- ── A norm violation ──────────────────────────────────────────────── -->
  <li v-else-if="entry.type === 'violation'" class="normnet-item">
    <div class="normnet-item__marker normnet-item__marker--violation" aria-hidden="true">!</div>
    <article class="rvo-alert rvo-alert--error rvo-alert--padding-md normnet-card">
      <h3 class="normnet-card__title">
        {{ expert ? `Norm ${entry.normId} geschonden` : 'Norm geschonden' }}
        <span class="rvo-tag rvo-tag--error rvo-tag--pill">
          {{ entry.kind === 'obligation' ? 'verplichting' : 'verbod' }}
        </span>
      </h3>
      <p class="normnet-card__violation">{{ entry.message }}</p>
      <p v-if="expert" class="normnet-card__violation-note">
        Vastgesteld in ronde {{ entry.round }} door de declaratieve laag, tegen de
        <em>ground marking</em> — niet achteraf uit een logbestand afgeleid.
      </p>
      <p v-else class="normnet-card__violation-note">
        Vastgesteld tijdens de run zelf, in ronde {{ entry.round }} — niet
        achteraf uit een logbestand afgeleid.
      </p>
    </article>
  </li>

  <!-- ── The run finished ──────────────────────────────────────────────── -->
  <li v-else-if="entry.type === 'finish'" class="normnet-item">
    <div class="normnet-item__marker normnet-item__marker--finish" aria-hidden="true">✓</div>
    <article
      class="rvo-alert rvo-alert--padding-md normnet-card"
      :class="entry.compliant ? 'rvo-alert--success' : 'rvo-alert--error'"
    >
      <h3 class="normnet-card__title">Run afgerond — {{ outcomeLabel(entry.outcome) }}</h3>
      <dl class="normnet-summary">
        <div><dt>Doorlooptijd</dt><dd>{{ formatHours(entry.elapsedHours) }}</dd></div>
        <div><dt>Overdrachten</dt><dd>{{ entry.handoffs }}</dd></div>
        <div><dt>Menselijke handelingen</dt><dd>{{ entry.humanTouches }}</dd></div>
        <div>
          <dt>Normen</dt>
          <dd>{{ entry.compliant ? 'geen schending' : 'geschonden' }}</dd>
        </div>
        <div v-if="expert">
          <dt>Replay tegen het model</dt>
          <dd>{{ entry.replayOk ? 'geldig vuurspoor' : 'ONGELDIG' }}</dd>
        </div>
      </dl>
      <!-- The engine's replay verdict is an English one-liner meant for the CLI;
           the page says it in Dutch and keeps the technical detail for a failure,
           where the marking and step index are the whole point. -->
      <p v-if="expert" class="normnet-card__replay">
        <template v-if="entry.replayOk">
          Het vuurspoor is opnieuw afgespeeld tegen het model en is geldig.
        </template>
        <template v-else>
          Het vuurspoor is <strong>niet</strong> geldig — {{ entry.replayMessage }}
        </template>
      </p>
      <details v-if="expert" class="rvo-expandable-content">
        <summary>Vuurspoor ({{ entry.firingSequence.length }} stappen)</summary>
        <ol class="normnet-sequence">
          <li v-for="(t, i) in entry.firingSequence" :key="`${t}-${i}`"><code>{{ t }}</code></li>
        </ol>
      </details>
    </article>
  </li>

  <!-- ── Something went wrong ──────────────────────────────────────────── -->
  <li v-else class="normnet-item">
    <div class="normnet-item__marker normnet-item__marker--violation" aria-hidden="true">!</div>
    <article class="rvo-alert rvo-alert--error rvo-alert--padding-md normnet-card">
      <h3 class="normnet-card__title">Fout</h3>
      <!-- The engine's errors carry setup instructions on their own lines —
           "start ollama", "pull this model" — so the line breaks are content. -->
      <p class="normnet-card__error">{{ entry.message }}</p>
    </article>
  </li>
</template>

<script setup lang="ts">
import ExecutorBadge from './ExecutorBadge.vue'
import {
  actorLabel,
  decisionLabel,
  executorMeta,
  factLabel,
  factValue,
  isKnownFact,
  netLabel,
} from '../labels'
import type { TimelineEntry } from '../types'
import { useViewMode } from '../useViewMode'

defineProps<{ entry: TimelineEntry }>()

const { expert } = useViewMode()

function learnedFacts(facts: Record<string, unknown>): [string, unknown][] {
  const entries = Object.entries(facts)
  return expert.value ? entries : entries.filter(([key]) => isKnownFact(key))
}

function formatHours(h: number): string {
  if (h < 1 / 60) return `${Math.round(h * 3600)} s`
  if (h < 1) return `${Math.round(h * 60)} min`
  if (h < 48) return `${h.toFixed(1)} uur`
  return `${(h / 24).toFixed(1)} dagen`
}

function outcomeLabel(outcome: string): string {
  return (
    {
      approved: 'goedgekeurd',
      rejected: 'afgewezen',
      'auto-settled': 'direct afgehandeld',
      unresolved: 'niet afgerond',
    }[outcome] ?? outcome
  )
}
</script>

<style scoped>
.normnet-item {
  display: grid;
  grid-template-columns: 2rem 1fr;
  gap: 0.75rem;
  margin-block-end: 1rem;
}
.normnet-item__marker {
  inline-size: 2rem;
  block-size: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--rvo-color-wit, #fff);
  background: var(--normnet-color-auto, #007bc7);
  margin-block-start: 0.5rem;
}
.normnet-item__marker--decision {
  background: var(--rvo-color-lintblauw, #154273);
}
.normnet-item__marker--violation {
  background: var(--normnet-color-violation, #d52b1e);
}
.normnet-item__marker--finish {
  background: var(--normnet-color-ok, #39870c);
}
.normnet-card {
  background-color: var(--normnet-color-surface, #fff);
}
.normnet-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.normnet-card__title {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  font-weight: 700;
}
.normnet-card__round {
  font-weight: 400;
  color: var(--normnet-color-text-muted, #4b5563);
  font-size: 0.875rem;
  margin-inline-start: 0.5rem;
}
.normnet-card__pending {
  margin: 0;
  font-style: italic;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-card__answer {
  margin: 0 0 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.normnet-card__answer-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-card__meta {
  font-size: 0.75rem;
}
.normnet-card__rationale {
  margin: 0 0 0.75rem;
  padding-inline-start: 0.75rem;
  border-inline-start: 3px solid var(--normnet-color-border-strong, #94a3b8);
  font-style: italic;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-card__human {
  margin: 0 0 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.875rem;
}
.normnet-card__concurrent-note {
  margin: 0 0 0.75rem;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
  max-inline-size: 80ch;
}
.normnet-transition {
  padding-block: 0.6rem;
  border-block-start: 1px solid var(--normnet-color-border, #e2e8f0);
}
.normnet-transition:first-of-type {
  border-block-start: 0;
  padding-block-start: 0;
}
.normnet-transition__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.normnet-transition__label {
  font-weight: 600;
}
.normnet-transition__id,
code {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-size: 0.75rem;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.1em 0.35em;
  border-radius: 2px;
}
.normnet-transition__actor {
  margin: 0.25rem 0 0;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-transition__note {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
}
.normnet-transition__facts {
  margin: 0.35rem 0 0;
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  align-items: baseline;
}
.normnet-transition__facts-label {
  font-size: 0.75rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-fact {
  font-size: 0.75rem;
  background: var(--normnet-color-page-bg, #f1f5f9);
  padding: 0.1em 0.4em;
  border-radius: 2px;
}
/* Raw engine keys read as code; the Dutch labels do not. */
.normnet-fact--raw {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
}
.normnet-card__prompt {
  margin-block-start: 0.5rem;
  font-size: 0.875rem;
}
.normnet-prompt__heading {
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
  margin: 0.75rem 0 0.25rem;
}
.normnet-prompt__text {
  margin: 0;
  padding: 0.6rem 0.75rem;
  background: var(--normnet-color-page-bg, #f1f5f9);
  border-radius: 3px;
  font-size: 0.8125rem;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}
.normnet-prompt__note {
  margin: 0.4rem 0 0;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-prompt__options {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin: 0;
}
.normnet-card__violation {
  margin: 0 0 0.4rem;
  font-weight: 600;
}
.normnet-card__violation-note,
.normnet-card__replay {
  margin: 0 0 0.5rem;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.75rem;
  margin: 0 0 0.75rem;
}
.normnet-summary dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-summary dd {
  margin: 0;
  font-weight: 700;
}
.normnet-sequence {
  margin: 0.5rem 0 0;
  padding-inline-start: 1.25rem;
  columns: 2;
  font-size: 0.8125rem;
}

.normnet-card__who {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.normnet-card__backend {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
  font-size: 0.6875rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
.normnet-card__who-line {
  margin: 0 0 0.6rem;
  font-size: 0.8125rem;
  color: var(--normnet-color-text-muted, #4b5563);
}
/* The explanation of the badge, one line, muted: it is there for the first
   read and must not compete with the note the step produced. */
.normnet-transition__how {
  color: var(--normnet-color-text-subtle, #64748b);
}
.normnet-card__error {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
