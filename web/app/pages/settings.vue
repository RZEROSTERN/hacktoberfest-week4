<script setup lang="ts">
import type { Schedule } from '~/types/api'
import { describeSchedule, spansMidnight } from '~/utils/schedule'

const { settings, saving, load, save } = useSettings()
await load()

const draft = ref<Schedule | null>(settings.value ? { ...settings.value.schedule } : null)

async function saveSchedule() {
  if (draft.value) await save({ schedule: draft.value })
}

async function toggleSensitive(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  await save({ index_sensitive_text: checked })
}
</script>

<template>
  <section v-if="settings && draft">
    <h1>Settings</h1>

    <h2>When to sort</h2>
    <p class="muted">{{ describeSchedule(draft) }}</p>

    <label class="row">
      <input v-model="draft.enabled" type="checkbox"> Sort automatically
    </label>

    <div class="row times">
      <label>From <input v-model="draft.windowStart" type="time"></label>
      <label>until <input v-model="draft.windowEnd" type="time"></label>
      <span v-if="spansMidnight(draft)" class="muted small">(overnight)</span>
    </div>

    <label class="row">
      <input v-model="draft.requireIdle" type="checkbox"> Only while I am away from the computer
    </label>
    <label class="row">
      <input v-model="draft.pauseOnBattery" type="checkbox"> Pause when running on battery
    </label>

    <button :disabled="saving" @click="saveSchedule">
      {{ saving ? 'Saving…' : 'Save schedule' }}
    </button>

    <h2>Privacy</h2>
    <label class="row">
      <input
        :checked="settings.index_sensitive_text"
        type="checkbox"
        @change="toggleSensitive"
      >
      Let me search inside sensitive screenshots
    </label>
    <p class="muted small">
      Off by default. Screenshots holding passwords, card numbers, bank details or
      verification codes are still sorted, but their text is never stored, so it cannot be
      searched or leak into a backup of the index.
    </p>

    <h2>Model</h2>
    <p class="muted">
      <template v-if="settings.vision_model">
        Using <strong>{{ settings.vision_model }}</strong>, running on this computer.
        Images are downscaled to {{ settings.max_image_px }} px before it sees them.
      </template>
      <template v-else>No model chosen yet.</template>
    </p>

    <p class="muted small"><NuxtLink to="/">← Back</NuxtLink></p>
  </section>
</template>

<style scoped>
h2 { font-size: 1.05rem; margin: 1.75rem 0 .5rem; }
.row { display: flex; align-items: center; gap: .5rem; margin: .5rem 0; }
.times { gap: 1rem; flex-wrap: wrap; }
.times label { display: flex; align-items: center; gap: .4rem; }
input[type="time"] { padding: .35rem .5rem; border: 1px solid var(--line); border-radius: 6px;
                     background: var(--bg); color: var(--fg); font: inherit; }
button { margin-top: .75rem; padding: .5rem 1rem; border: 1px solid var(--line);
         border-radius: 8px; background: var(--bg); color: var(--fg); font: inherit;
         cursor: pointer; }
.small { font-size: .875rem; }
</style>
