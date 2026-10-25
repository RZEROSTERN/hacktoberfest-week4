/**
 * When a run is allowed to happen.
 *
 * All of the deciding is here, as one pure function over a snapshot of conditions, so the
 * rules can be tested without a machine that is actually idle or actually on battery.
 *
 * Why conditions are polled rather than subscribed to: Electron documents `on-battery` and
 * `on-ac` as macOS and Windows only, so a Linux build that waited for those events would never
 * notice the power state changing. `powerMonitor.onBatteryPower` and `getSystemIdleTime()`
 * carry no platform restriction, so reading them on a timer behaves the same everywhere.
 */

export interface Schedule {
  enabled: boolean
  /** Local wall-clock times, "HH:MM". A start later than the end means the window spans midnight. */
  windowStart: string
  windowEnd: string
  requireIdle: boolean
  idleThresholdSeconds: number
  pauseOnBattery: boolean
}

export interface Conditions {
  now: Date
  idleSeconds: number
  onBattery: boolean
}

export type Blocker = 'disabled' | 'outside-window' | 'in-use' | 'on-battery'

export type Decision =
  | { run: true }
  | { run: false; because: Blocker }

export const DEFAULT_SCHEDULE: Schedule = {
  enabled: true,
  // Overnight by default: the machine is usually idle, plugged in, and nobody is waiting.
  windowStart: '23:00',
  windowEnd: '07:00',
  requireIdle: true,
  idleThresholdSeconds: 300,
  pauseOnBattery: true,
}

/** Minutes since midnight, or null when the text is not a time. */
export function minutesOf(hhmm: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim())
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (hours > 23 || minutes > 59) return null
  return hours * 60 + minutes
}

/**
 * Whether `now` falls inside the window, handling the ordinary case where it spans midnight.
 * The window is inclusive of its start and exclusive of its end.
 */
export function inWindow(now: Date, windowStart: string, windowEnd: string): boolean {
  const start = minutesOf(windowStart)
  const end = minutesOf(windowEnd)
  if (start === null || end === null) return false
  if (start === end) return true // a zero-length window is read as "any time"

  const current = now.getHours() * 60 + now.getMinutes()
  return start < end
    ? current >= start && current < end
    : current >= start || current < end // spans midnight
}

/** The one decision. Checked in the order a user would expect to be told about. */
export function shouldRun(schedule: Schedule, conditions: Conditions): Decision {
  if (!schedule.enabled) return { run: false, because: 'disabled' }
  if (!inWindow(conditions.now, schedule.windowStart, schedule.windowEnd)) {
    return { run: false, because: 'outside-window' }
  }
  if (schedule.pauseOnBattery && conditions.onBattery) {
    return { run: false, because: 'on-battery' }
  }
  if (schedule.requireIdle && conditions.idleSeconds < schedule.idleThresholdSeconds) {
    return { run: false, because: 'in-use' }
  }
  return { run: true }
}

/** What the tray says it is waiting for. Never blames the user for using their computer. */
export function explain(blocker: Blocker): string {
  switch (blocker) {
    case 'disabled':
      return 'Scheduled sorting is off'
    case 'outside-window':
      return 'Waiting for the scheduled time'
    case 'in-use':
      return 'Waiting until you step away'
    case 'on-battery':
      return 'Waiting until you plug in'
  }
}
