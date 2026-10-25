import type { AppSettings, Schedule } from '~/types/api'

export function useSettings() {
  const { apiFetch } = useApi()
  const settings = ref<AppSettings | null>(null)
  const saving = ref(false)

  async function load() {
    settings.value = await apiFetch<AppSettings>('/api/settings')
  }

  async function save(changes: { schedule?: Schedule, index_sensitive_text?: boolean }) {
    saving.value = true
    try {
      settings.value = await apiFetch<AppSettings>('/api/settings', {
        method: 'PUT',
        body: changes,
      })
    } finally {
      saving.value = false
    }
  }

  return { settings, saving, load, save }
}
