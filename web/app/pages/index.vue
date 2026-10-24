<script setup lang="ts">
import type { AppStatus } from '~/types/api'

const { apiFetch } = useApi()
const { data: status, error } = await useAsyncData('status', () =>
  apiFetch<AppStatus>('/api/status')
)
</script>

<template>
  <section>
    <h1>Slothshot</h1>
    <p class="muted">Sorts your screenshots while you are not using your computer.</p>

    <p v-if="error">The app's local service is not running yet.</p>
    <p v-else-if="status?.vision_model">
      Using <strong>{{ status.vision_model }}</strong>.
    </p>
    <p v-else>No model chosen yet.</p>
  </section>
</template>
