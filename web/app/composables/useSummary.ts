import type { Summary } from '~/types/api'

export function useSummary() {
  const { apiFetch } = useApi()
  return useAsyncData('summary', () => apiFetch<Summary>('/api/summary'))
}
