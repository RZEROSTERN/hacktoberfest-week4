import type { Summary } from '~/types/api'
import { formatBytes, pluralize } from './format'

/** The card's headline. Says nothing about what any screenshot contains. */
export function headline(summary: Summary): string {
  if (summary.run_id === null) return 'Nothing sorted yet.'
  if (summary.sorted_count === 0) return 'Nothing new to sort.'
  return `Sorted ${pluralize(summary.sorted_count, 'screenshot')}.`
}

/** The Review line, or null when there is nothing waiting. */
export function reviewLine(summary: Summary): string | null {
  const waiting = summary.duplicates_waiting + summary.expired_waiting
  if (waiting === 0) return null

  const parts: string[] = []
  if (summary.duplicates_waiting > 0) {
    parts.push(pluralize(summary.duplicates_waiting, 'duplicate'))
  }
  if (summary.expired_waiting > 0) parts.push(`${summary.expired_waiting} expired`)
  return `${parts.join(' and ')} waiting in Review.`
}

/**
 * What deleting the Review items by hand would free. Phrased as information, not an offer:
 * Slothshot never deletes anything itself.
 */
export function reclaimLine(summary: Summary): string | null {
  if (summary.reclaimable_bytes <= 0) return null
  return `Deleting them yourself would free ${formatBytes(summary.reclaimable_bytes)}.`
}

export function skippedLine(summary: Summary): string | null {
  if (summary.skipped_count === 0) return null
  return `${pluralize(summary.skipped_count, 'screenshot')} could not be read and ${
    summary.skipped_count === 1 ? 'was' : 'were'
  } left alone.`
}
