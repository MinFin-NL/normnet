<template>
  <header data-rvo-on-dark class="normnet-header">
    <div class="rvo-max-width-layout rvo-max-width-layout--lg rvo-max-width-layout-inline-padding--sm">
      <div class="normnet-header__topbar">
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
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import emblemUrl from '@nl-rvo/assets/images/emblem.svg'
</script>

<style scoped>
.normnet-header {
  background-color: var(--rvo-color-hemelblauw, #007bc7);
  color: var(--rvo-color-wit, #fff);
  padding-block: 1rem;
}
.normnet-header__topbar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.normnet-header__logo :deep(.rvo-logo__title) {
  white-space: pre-line;
  margin: 0;
}
.normnet-header__titles {
  border-inline-start: 1px solid rgb(255 255 255 / 45%);
  padding-inline-start: 1.5rem;
}
.normnet-header__app {
  margin: 0;
  font-size: 1.375rem;
  font-weight: 700;
  line-height: 1.2;
}
.normnet-header__tagline {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  max-inline-size: 46ch;
}
@media (max-width: 640px) {
  .normnet-header__titles {
    border-inline-start: 0;
    padding-inline-start: 0;
  }
}
</style>
