<script setup lang="ts">
import { headline, reclaimLine, reviewLine, skippedLine } from '~/utils/summary'

const { data: summary, error } = await useSummary()
</script>

<template>
  <section>
    <h1>Slothshot</h1>
    <p class="muted">Sorts your screenshots while you are not using your computer.</p>

    <p v-if="error" class="muted">The app's local service is not running yet.</p>

    <article v-else-if="summary" class="card">
      <h2>{{ headline(summary) }}</h2>
      <p v-if="reviewLine(summary)">{{ reviewLine(summary) }}</p>
      <p v-if="reclaimLine(summary)" class="muted">{{ reclaimLine(summary) }}</p>
      <p v-if="skippedLine(summary)" class="muted">{{ skippedLine(summary) }}</p>
      <p class="muted small">
        {{ summary.total_indexed }} screenshots indexed. Nothing is ever deleted, and every
        change can be undone.
      </p>
      <p class="links">
        <NuxtLink to="/search">Search your screenshots</NuxtLink>
        <NuxtLink to="/settings">Settings</NuxtLink>
      </p>
    </article>
  </section>
</template>

<style scoped>
.card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-top: 1.5rem;
}
.card h2 { margin: 0 0 .5rem; font-size: 1.25rem; }
.card p { margin: .25rem 0; }
.small { font-size: .875rem; margin-top: 1rem; }
.links { display: flex; gap: 1.25rem; margin-top: 1rem; }
</style>
