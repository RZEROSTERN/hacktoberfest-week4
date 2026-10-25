/**
 * A fresh install has no model, so there is nothing for the other screens to show. This sends
 * the user to the wizard once, rather than letting them find an empty app and wonder.
 *
 * It never redirects away from the wizard, and it stays out of the way if the api cannot be
 * reached: being unable to ask is not a reason to assume the worst.
 */
import type { SetupStatus } from '~/types/api'

export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path === '/setup') return
  const { apiFetch } = useApi()
  try {
    const status = await apiFetch<SetupStatus>('/api/setup/status')
    if (!status.ready) return navigateTo('/setup')
  }
  catch {
    // The api is not up yet. The screens handle that themselves.
  }
})
