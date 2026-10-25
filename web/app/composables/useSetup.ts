import type { SetupProgress, SetupStatus } from '~/types/api'

const POLL_MS = 1000

export function useSetup() {
  const { apiFetch } = useApi()
  const status = ref<SetupStatus | null>(null)
  const progress = ref<SetupProgress | null>(null)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    status.value = await apiFetch<SetupStatus>('/api/setup/status')
    progress.value = await apiFetch<SetupProgress>('/api/setup/progress')
  }

  function watchProgress() {
    if (timer) return
    timer = setInterval(() => void refresh().catch(() => {}), POLL_MS)
  }

  function stopWatching() {
    if (timer) clearInterval(timer)
    timer = null
  }

  async function post(path: string, body?: Record<string, unknown>) {
    error.value = null
    try {
      await apiFetch(path, { method: 'POST', body })
      await refresh()
    }
    catch (caught) {
      const data = (caught as { data?: { code?: string } }).data
      error.value = data?.code ?? 'setup_failed'
    }
  }

  const start = (model: string) => post('/api/setup/start', { model })
  const pause = () => post('/api/setup/pause')
  const resume = () => post('/api/setup/resume')

  onUnmounted(stopWatching)

  return { status, progress, error, refresh, watchProgress, stopWatching, start, pause, resume }
}
