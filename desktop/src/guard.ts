/**
 * The loop that decides when to sort.
 *
 * Conditions are read on a timer rather than from events, because Electron documents
 * `on-battery` and `on-ac` as macOS and Windows only; a Linux build waiting for those would
 * never notice the power state change. `onBatteryPower` and `getSystemIdleTime()` carry no
 * platform restriction.
 *
 * All the deciding lives in `schedule.ts`; this part only reads the machine and calls the api.
 */

import { type Blocker, type Conditions, type Schedule, shouldRun } from './schedule'

export const TICK_MS = 60_000

export interface Machine {
  idleSeconds: () => number
  onBattery: () => boolean
  now: () => Date
}

export interface Api {
  settings: () => Promise<{ schedule: Schedule; paused: boolean }>
  currentRun: () => Promise<{ id: number; status: string } | null>
  start: () => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
}

export interface Tick {
  started?: boolean
  paused?: boolean
  resumed?: boolean
  blocker: Blocker | null
  running: boolean
}

/**
 * One pass of the guard. Returns what it did, so the tray can say so and a test can check it.
 *
 * A run in flight is paused the moment conditions stop allowing it, and resumed when they
 * allow it again. A run is never started while one is already going.
 */
export async function tick(api: Api, machine: Machine): Promise<Tick> {
  const { schedule, paused } = await api.settings()
  const current = await api.currentRun()
  const conditions: Conditions = {
    now: machine.now(),
    idleSeconds: machine.idleSeconds(),
    onBattery: machine.onBattery(),
  }
  const decision = shouldRun(schedule, conditions)
  const blocker = decision.run ? null : decision.because
  const running = current !== null

  if (running) {
    if (!decision.run && !paused) {
      await api.pause()
      return { paused: true, blocker, running }
    }
    if (decision.run && paused) {
      await api.resume()
      return { resumed: true, blocker, running }
    }
    return { blocker, running }
  }

  if (decision.run) {
    await api.start()
    return { started: true, blocker: null, running: true }
  }
  return { blocker, running: false }
}
