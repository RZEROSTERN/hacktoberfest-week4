/**
 * The one notification a run is allowed to produce.
 *
 * The rules here exist so the app stays a good neighbour in the user's notification centre:
 * one notification per finished run, never for a run that did nothing, and never a second one
 * for a run already announced. An app that sorts files overnight becomes intolerable the
 * moment it starts reporting that it had nothing to do.
 *
 * The text never names a file or describes what any screenshot contains.
 */

export interface Summary {
  run_id: number | null
  sorted_count: number
  skipped_count: number
  duplicates_waiting: number
  expired_waiting: number
  reclaimable_bytes: number
  total_indexed: number
}

export interface Notification {
  title: string
  body: string
}

function plural(count: number, singular: string): string {
  return `${count} ${count === 1 ? singular : `${singular}s`}`
}

/** What to say about a finished run, or null when it does not deserve interrupting anyone. */
export function notificationFor(summary: Summary): Notification | null {
  if (summary.run_id === null || summary.sorted_count === 0) return null

  const waiting = summary.duplicates_waiting + summary.expired_waiting
  const body =
    waiting > 0
      ? `${plural(summary.sorted_count, 'screenshot')} sorted. ${plural(waiting, 'item')} waiting in Review.`
      : `${plural(summary.sorted_count, 'screenshot')} sorted.`

  return { title: 'Slothshot', body }
}

/**
 * Remembers which run was already announced, so a poll that sees the same finished run again
 * stays quiet.
 */
export class RunAnnouncer {
  private announced: number | null = null

  /** Returns the notification to show, or null. Marks the run as announced when it returns one. */
  consider(summary: Summary): Notification | null {
    if (summary.run_id === null || summary.run_id === this.announced) return null
    const notification = notificationFor(summary)
    // The run counts as seen either way, so a run that did nothing is not reconsidered later.
    this.announced = summary.run_id
    return notification
  }
}
