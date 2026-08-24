<template>
  <!-- The one label a reader should be able to find on every step without
       hunting: who did this. Colour alone never carries it — there is a glyph
       and a word, so it survives a colour-blind reader and a printout. -->
  <span
    class="normnet-exec"
    :class="[`normnet-exec--${kind}`, { 'normnet-exec--sm': small }]"
    :title="meta.explanation"
  >
    <span class="normnet-exec__icon" aria-hidden="true">{{ meta.icon }}</span>
    <span class="normnet-exec__text">{{ small ? meta.short : meta.label }}</span>
    <span v-if="llmAdvises" class="normnet-exec__advice">
      <span class="normnet-exec__sep" aria-hidden="true">·</span>
      model adviseert
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { executorMeta } from '../labels'
import type { ExecutorKind } from '../types'

const props = withDefaults(
  defineProps<{
    kind: ExecutorKind
    /** a human step the model wrote the recommendation for */
    llmAdvises?: boolean
    small?: boolean
  }>(),
  { llmAdvises: false, small: false },
)

const meta = computed(() => executorMeta(props.kind))
</script>

<style scoped>
.normnet-exec {
  display: inline-flex;
  align-items: baseline;
  gap: 0.3rem;
  padding: 0.1em 0.5em;
  border-radius: 999px;
  border: 1px solid currentColor;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.5;
  white-space: nowrap;
}
.normnet-exec--sm {
  font-size: 0.6875rem;
  padding: 0.05em 0.4em;
}
.normnet-exec__icon {
  font-size: 0.875em;
}
.normnet-exec__advice {
  font-weight: 400;
  opacity: 0.85;
}
.normnet-exec__sep {
  margin-inline-end: 0.15rem;
}

/* Three families, deliberately far apart: slate for code, purple for the
   model, amber for a person. The same three colours are used by the graph and
   the tracker, so the mapping only has to be learned once. */
.normnet-exec--deterministic {
  color: #334155;
  background: #f1f5f9;
  border-color: #cbd5e1;
}
.normnet-exec--llm {
  color: #5b2d90;
  background: #f4ecff;
  border-color: #c9aee8;
}
.normnet-exec--human {
  color: #8f5c2c;
  background: #fff4d9;
  border-color: #f0c766;
}
</style>
