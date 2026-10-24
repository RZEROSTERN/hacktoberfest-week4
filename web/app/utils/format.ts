/** Pure formatting helpers. No Nuxt runtime, so they are unit-testable on their own. */

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

/**
 * Human-readable size. Used by the morning card to say how much space sits in Review.
 * Binary steps (1024), decimal labels, which is what desktop file managers show.
 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${Math.round(bytes)} B`

  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  // One decimal below 10 so "1.4 GB" stays useful, none above so "237 MB" stays short.
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${UNITS[unit]}`
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

/**
 * The one-line morning card. Deliberately says nothing about what the screenshots contain.
 */
export function describeRun(run: {
  organized: number
  duplicates: number
  expired: number
}): string {
  const parts = [`Sorted ${pluralize(run.organized, 'screenshot')}`]
  const waiting = run.duplicates + run.expired
  if (waiting > 0) parts.push(`${pluralize(waiting, 'item')} waiting in Review`)
  return `${parts.join('. ')}.`
}
