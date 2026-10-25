import type { Schedule } from '~/types/api'

/** A plain sentence describing when sorting will happen. Shown above the controls. */
export function describeSchedule(schedule: Schedule): string {
  if (!schedule.enabled) return 'Scheduled sorting is off. You can still sort whenever you like.'

  const guards: string[] = []
  if (schedule.requireIdle) guards.push('while you are away from the computer')
  if (schedule.pauseOnBattery) guards.push('while it is plugged in')

  const when = `between ${schedule.windowStart} and ${schedule.windowEnd}`
  return guards.length > 0
    ? `Sorts ${when}, but only ${guards.join(' and ')}.`
    : `Sorts ${when}.`
}

/** Whether a window spans midnight, which the UI points out so it does not look like a typo. */
export function spansMidnight(schedule: Schedule): boolean {
  const [sh = 0, sm = 0] = schedule.windowStart.split(':').map(Number)
  const [eh = 0, em = 0] = schedule.windowEnd.split(':').map(Number)
  return sh * 60 + sm > eh * 60 + em
}
