import { APP_HOST, APP_SCHEME } from './env'

/** Pages the app may open in the user's own browser. Only the Ollama model library is linked. */
const EXTERNAL_HOSTS = new Set(['ollama.com'])

/**
 * The main process parses URLs with Node, which reports the origin of a custom scheme as "null",
 * so the scheme and host are compared instead.
 */
export function isAppUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === `${APP_SCHEME}:` && parsed.host === APP_HOST
  } catch {
    return false
  }
}

export function isAllowedExternal(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' && EXTERNAL_HOSTS.has(parsed.hostname)
  } catch {
    return false
  }
}

/** What a window may request: its own files, the local api, and the built-in start page. */
export function isAllowedRequest(url: string, apiOrigin: string): boolean {
  if (url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('devtools:')) return true
  if (isAppUrl(url)) return true
  try {
    return new URL(url).origin === apiOrigin
  } catch {
    return false
  }
}
