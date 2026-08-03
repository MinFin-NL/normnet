<template>
  <footer class="normnet-footer" role="contentinfo" aria-label="Bèta-melding">
    <div
      class="rvo-max-width-layout rvo-max-width-layout--lg rvo-max-width-layout-inline-padding--sm normnet-footer__inner"
    >
      <div class="rvo-alert rvo-alert--warning rvo-alert--padding-sm normnet-footer__alert">
        <div class="rvo-alert__container">
          <p class="rvo-text rvo-text--sm normnet-footer__text">
            Proof of concept — niet productierijp. Vragen of feedback?
            <a
              class="rvo-link"
              href="mailto:innovatiemanagamentfinancien@minfin.nl"
            >innovatiemanagamentfinancien@minfin.nl</a>
            ·
            <a
              class="rvo-link"
              href="https://github.com/MinFin-NL/normnet"
            >github.com/MinFin-NL/normnet</a>
          </p>
        </div>
      </div>
    </div>
  </footer>
</template>

<style scoped>
/* Fixed overlay strip, as in invulhulp: `none` on the bar so it never eats a
   click on the page beneath it, `auto` on the inner box that is actually
   visible. `.normnet-main` reserves the matching space at the bottom. */
.normnet-footer {
  position: fixed;
  inset-block-end: 0;
  inset-inline: 0;
  z-index: 100;
  pointer-events: none;
}

.normnet-footer__inner {
  pointer-events: auto;
  padding-block: 3px;
  padding-inline: var(--rvo-space-md);
}

.normnet-footer__alert {
  text-align: center;
}

.normnet-footer__text {
  margin: 0;
}
</style>
