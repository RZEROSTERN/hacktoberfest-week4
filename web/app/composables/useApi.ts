/** API base URL: from the desktop preload when packaged, otherwise from runtimeConfig. */
export function resolveApiBase(preloadBase: string | undefined, configBase: string): string {
  return (preloadBase || configBase).replace(/\/+$/, '')
}

export function useApi() {
  const config = useRuntimeConfig()
  const base = resolveApiBase(
    import.meta.client ? window.desktop?.apiBase : undefined,
    config.public.apiBase
  )

  function apiFetch<T>(path: string, options?: Parameters<typeof $fetch>[1]) {
    return $fetch<T>(`${base}${path}`, options)
  }

  return { base, apiFetch }
}
