<template>
  <!-- One glyph per executor, drawn as a mask so it takes the colour of the
       badge it sits in — the same icon has to read on a slate, a purple and an
       amber ground. Regel and Mens come from the NL Design System icon set;
       Model is the sparkle FinChat uses, so the ministry's own AI mark means
       the same thing here as it does on the dashboard. -->
  <span
    class="normnet-icon"
    :class="`normnet-icon--${kind}`"
    :style="{ '--normnet-icon-size': size }"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import type { ExecutorKind } from '../types'

withDefaults(defineProps<{ kind: ExecutorKind; size?: string }>(), {
  size: '1em',
})
</script>

<style scoped>
.normnet-icon {
  display: inline-block;
  inline-size: var(--normnet-icon-size, 1em);
  block-size: var(--normnet-icon-size, 1em);
  flex: none;
  background-color: currentColor;
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}
/* Static url() on purpose — a runtime one does not survive the production
   build (see the note on --rvo-icon-* in main.css). */
.normnet-icon--deterministic {
  -webkit-mask-image: url('@nl-rvo/assets/icons/gereedschap/tandwiel-met-vinkje.svg');
  mask-image: url('@nl-rvo/assets/icons/gereedschap/tandwiel-met-vinkje.svg');
}
.normnet-icon--llm {
  -webkit-mask-image: url('../assets/icons/model-sparkle.svg');
  mask-image: url('../assets/icons/model-sparkle.svg');
}
.normnet-icon--human {
  -webkit-mask-image: url('@nl-rvo/assets/icons/functioneel/user.svg');
  mask-image: url('@nl-rvo/assets/icons/functioneel/user.svg');
}
</style>
