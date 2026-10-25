import type { SearchResults } from '~/types/api'

export function useSearch() {
  const { apiFetch } = useApi()
  const query = ref('')
  const results = ref<SearchResults | null>(null)
  const searching = ref(false)

  async function run() {
    const q = query.value.trim()
    if (!q) {
      results.value = null
      return
    }
    searching.value = true
    try {
      results.value = await apiFetch<SearchResults>('/api/search', { query: { q } })
    } finally {
      searching.value = false
    }
  }

  return { query, results, searching, run }
}
