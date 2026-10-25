<script setup lang="ts">
import { formatBytes } from '~/utils/format'
import { canResume, downloadLine, isBusy, modelCost } from '~/utils/setup'

const { status, progress, error, refresh, watchProgress, start, pause, resume } = useSetup()
const advanced = ref(false)
const customModel = ref('')

await refresh()
watchProgress()

const messages: Record<string, string> = {
  compat_no_vision: 'That model could not read a test image, so it cannot sort screenshots. Choose one of the recommended models.',
  compat_invalid_output: 'That model did not return the structured answer the app needs, even after a retry.',
  compat_timeout: 'That model took too long on a small test image. It may be too big for this computer.',
  cloud_model: 'Cloud models send your screenshots to a server. Slothshot only uses models that run on this computer.',
  invalid_model_name: 'That is not a valid model name. Use name:tag, for example qwen3-vl:2b-instruct.',
  model_not_found: 'No model with that name exists in the Ollama library. Check the name and tag.',
  network_error: 'The download stopped because the connection was lost. Continuing picks up where it left off.',
  not_enough_disk: 'There is not enough free disk space for this download.',
  ollama_unreachable: 'The local AI engine is not running yet.',
  setup_busy: 'A download is already in progress.',
}

function explain(code: string | null): string | null {
  return code ? (messages[code] ?? 'Something went wrong. You can try again.') : null
}
</script>

<template>
  <section v-if="status && progress">
    <h1>Set up Slothshot</h1>

    <!-- Ready -->
    <template v-if="status.ready && !isBusy(progress)">
      <p>Slothshot is ready, using <strong>{{ status.model.model }}</strong>.</p>
      <p class="muted small">It runs on this computer. Your screenshots are never uploaded.</p>
      <NuxtLink to="/">Continue →</NuxtLink>
    </template>

    <!-- Working -->
    <template v-else-if="isBusy(progress)">
      <p class="muted">Setting up <strong>{{ progress.model }}</strong>.</p>
      <div class="bar"><div class="fill" :style="{ width: `${Math.round(progress.overall.fraction * 100)}%` }" /></div>

      <ol class="steps">
        <li v-for="step in progress.steps" :key="step.id" :class="step.state">
          <span class="mark">{{ step.state === 'done' ? '✓' : step.state === 'running' ? '•' : '' }}</span>
          <div>
            {{ step.label }}<span v-if="step.skipped" class="muted small"> — already on this computer</span>
            <p v-if="downloadLine(step)" class="muted small">{{ downloadLine(step) }}</p>
          </div>
        </li>
      </ol>

      <button @click="pause">Pause</button>
      <p class="muted small">Pausing keeps what has downloaded. Continuing picks up from there.</p>
    </template>

    <!-- Needs a decision -->
    <template v-else>
      <p v-if="!status.ollama_reachable" class="notice">
        The local AI engine is not running yet. It starts with the app; give it a moment.
      </p>

      <p v-if="explain(progress.error_code)" class="notice">{{ explain(progress.error_code) }}</p>
      <p v-if="error" class="notice">{{ explain(error) }}</p>

      <template v-if="canResume(progress)">
        <p>
          A download of <strong>{{ progress.model }}</strong> was interrupted at
          {{ Math.round(progress.overall.fraction * 100) }}%.
        </p>
        <button @click="resume">Continue that download</button>
        <p class="muted small">Or choose a different model below.</p>
      </template>

      <h2>Choose a model</h2>
      <p class="muted">
        Slothshot reads your screenshots with a model that runs on this computer. It is
        downloaded once, from the Ollama library, and it is the only thing this app ever
        downloads.
      </p>

      <ul class="models">
        <li v-for="model in status.recommended" :key="model.model">
          <div class="head">
            <strong>{{ model.title }}</strong>
            <span v-if="model.recommended" class="tag">recommended</span>
          </div>
          <code>{{ model.model }}</code>
          <p class="muted small">{{ modelCost(model) }}</p>
          <p class="small">{{ model.note }}</p>
          <button :disabled="isBusy(progress)" @click="start(model.model)">
            Download {{ formatBytes(model.size_bytes) }}
          </button>
        </li>
      </ul>

      <p class="small">
        <button class="link" @click="advanced = !advanced">
          {{ advanced ? 'Hide' : 'Use a different model' }}
        </button>
      </p>
      <div v-if="advanced" class="advanced">
        <p class="muted small">
          Any vision model from the Ollama library. It is checked against a test image before
          Slothshot will use it, so a model that cannot read images is refused rather than
          silently producing nonsense.
        </p>
        <div class="row">
          <input v-model="customModel" placeholder="name:tag" aria-label="Model name">
          <button :disabled="!customModel.trim() || isBusy(progress)" @click="start(customModel.trim())">
            Download
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
h2 { font-size: 1.05rem; margin: 1.75rem 0 .5rem; }
.bar { height: 8px; border-radius: 999px; background: var(--line); overflow: hidden; margin: 1rem 0; }
.fill { height: 100%; background: #3884ff; transition: width .4s ease; }
.steps { list-style: none; padding: 0; }
.steps li { display: flex; gap: .6rem; padding: .35rem 0; color: var(--muted); }
.steps li.running, .steps li.done { color: var(--fg); }
.steps li.failed { color: #dc443e; }
.steps p { margin: .15rem 0 0; }
.mark { width: 1rem; }
.models { list-style: none; padding: 0; display: grid; gap: 1rem; }
.models li { border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.25rem; }
.models .head { display: flex; align-items: center; gap: .6rem; }
.models code { font-size: .8rem; color: var(--muted); }
.models p { margin: .35rem 0; }
.tag { font-size: .7rem; border: 1px solid var(--line); border-radius: 999px; padding: .1rem .5rem; color: var(--muted); }
.notice { border-left: 3px solid #dc443e; padding-left: .75rem; }
button { padding: .5rem 1rem; border: 1px solid var(--line); border-radius: 8px;
         background: var(--bg); color: var(--fg); font: inherit; cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
button.link { border: 0; padding: 0; text-decoration: underline; }
.advanced .row { display: flex; gap: .5rem; margin-top: .5rem; }
.advanced input { flex: 1; padding: .5rem .6rem; border: 1px solid var(--line); border-radius: 8px;
                  background: var(--bg); color: var(--fg); font: inherit; }
.small { font-size: .875rem; }
</style>
