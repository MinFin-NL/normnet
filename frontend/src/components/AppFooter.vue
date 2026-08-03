<template>
  <footer class="normnet-footer">
    <div class="rvo-max-width-layout rvo-max-width-layout--lg rvo-max-width-layout-inline-padding--sm">
      <p class="normnet-footer__text">
        <strong>NormNet</strong> — auditeerbare procesautomatisering met LLM's.
        Het procedurele deel (petrinet) begrenst wat <em>mogelijk</em> is, het
        declaratieve deel (normen) begrenst wat <em>toegestaan</em> is.
      </p>
      <p class="normnet-footer__text normnet-footer__muted">
        Declaratieve laag naar Sileno (2020),
        <span lang="en">Logic Programming Petri Nets</span>, Universiteit van Amsterdam.
        Proof of concept — niet productierijp.
      </p>
    </div>
  </footer>
</template>

<style scoped>
.normnet-footer {
  margin-block-start: 3rem;
  padding-block: 1.5rem;
  border-block-start: 1px solid var(--normnet-color-border-strong, #cbd5e1);
  background-color: var(--normnet-color-surface, #fff);
}
.normnet-footer__text {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  max-inline-size: 90ch;
}
.normnet-footer__muted {
  color: var(--normnet-color-text-muted, #4b5563);
  margin-block-end: 0;
}
</style>
