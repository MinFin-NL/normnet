<template>
  <header data-rvo-on-dark class="normnet-header">
    <div class="rvo-max-width-layout rvo-max-width-layout--lg rvo-max-width-layout-inline-padding--sm">
      <div class="rvo-layout-row rvo-layout-gap--md normnet-header__topbar">
        <div class="rvo-logo normnet-header__logo">
          <img class="rvo-logo__emblem" :src="emblemUrl" alt="" />
          <div class="rvo-logo__wordmark">
            <p class="rvo-logo__title">Ministerie van&#10;Financiën</p>
          </div>
        </div>
        <div class="normnet-header__titles">
          <p class="normnet-header__app">NormNet</p>
          <p class="normnet-header__tagline">
            Stap voor stap inzien wat het proces doet, wat het model besluit en
            waar het op u wacht
          </p>
        </div>
        <div class="normnet-header__actions">
          <button
            type="button"
            class="normnet-header__ghost-btn"
            :aria-pressed="expert"
            @click="expert = !expert"
          >
            Technische details
            <span class="normnet-header__switch" :class="{ 'normnet-header__switch--on': expert }">
              <span class="normnet-header__switch-knob" />
            </span>
            <span class="normnet-visually-hidden">
              {{ expert ? 'staat aan' : 'staat uit' }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import emblemUrl from '@nl-rvo/assets/images/emblem.svg'
import { useViewMode } from '../useViewMode'

const { expert } = useViewMode()
</script>

<style scoped>
.normnet-header {
  background-color: var(--rvo-color-lintblauw);
  color: var(--rvo-color-wit);
  padding: 0;
}
.normnet-header__topbar {
  display: flex;
  align-items: center;
  gap: var(--rvo-space-md);
  flex-wrap: wrap;
  padding-block: var(--rvo-space-sm);
}
.normnet-header__logo {
  --rvo-logo-color: var(--rvo-color-wit);
  --rvo-logo-font-family: inherit;
  --rvo-logo-font-weight: bold;
}
.normnet-header__logo :deep(.rvo-logo__title) {
  white-space: pre-line;
  margin: 0;
}
.normnet-header__titles {
  border-inline-start: 1px solid rgb(255 255 255 / 0.45);
  padding-inline-start: var(--rvo-space-md);
}
.normnet-header__app {
  margin: 0;
  font-size: var(--rvo-font-size-xl, 1.375rem);
  font-weight: var(--rvo-font-weight-bold, 700);
  line-height: var(--rvo-line-height-sm, 1.25);
}
.normnet-header__tagline {
  margin: var(--rvo-space-2xs) 0 0;
  font-size: var(--rvo-font-size-sm);
  max-inline-size: 46ch;
}

/* Trailing action cluster, ghost-styled like invulhulp's header buttons: plain
   translucent text rather than a bordered rvo-button, which would read as the
   primary action of the page. */
.normnet-header__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--rvo-space-sm);
  margin-inline-start: auto;
}
.normnet-header__ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--rvo-space-xs);
  border: 0;
  background: transparent;
  color: rgb(255 255 255 / 0.75);
  font: inherit;
  font-size: var(--rvo-font-size-sm);
  font-weight: var(--rvo-font-weight-semibold);
  white-space: nowrap;
  padding: var(--rvo-space-3xs) var(--rvo-space-xs);
  border-radius: var(--rvo-radius-md, 4px);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.normnet-header__ghost-btn:hover {
  background: rgb(255 255 255 / 0.12);
  color: var(--rvo-color-wit);
}
.normnet-header__ghost-btn:focus-visible {
  outline: 2px solid var(--rvo-color-wit);
  outline-offset: 2px;
}

/* Switch affordance. Purely decorative — the state is carried by aria-pressed
   and the visually-hidden "staat aan/uit", so it is never colour-only. */
.normnet-header__switch {
  inline-size: 2rem;
  block-size: 1.125rem;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.25);
  border: 1px solid rgb(255 255 255 / 0.5);
  display: inline-flex;
  align-items: center;
  padding: 2px;
  transition: background 0.15s;
}
.normnet-header__switch--on {
  background: var(--rvo-color-groen, #39870c);
  border-color: var(--rvo-color-wit);
}
.normnet-header__switch-knob {
  inline-size: 0.75rem;
  block-size: 0.75rem;
  border-radius: 50%;
  background: var(--rvo-color-wit);
  transition: transform 0.15s;
}
.normnet-header__switch--on .normnet-header__switch-knob {
  transform: translateX(0.875rem);
}

@media (max-width: 640px) {
  .normnet-header__titles {
    border-inline-start: 0;
    padding-inline-start: 0;
  }
  .normnet-header__actions {
    margin-inline-start: 0;
  }
}
</style>
