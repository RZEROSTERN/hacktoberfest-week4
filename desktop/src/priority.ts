import os from 'node:os'

/**
 * Process priority for the api and the bundled Ollama, so a run never competes with whatever the
 * user is doing.
 *
 * `os.setPriority` is the one call that works on all three platforms: on Windows Node maps the
 * range onto the priority classes, and on macOS and Linux it is nice(2). BELOW_NORMAL is used
 * rather than the lowest setting because Windows maps the bottom of the range to
 * IDLE_PRIORITY_CLASS, where a run on a busy machine can be starved indefinitely instead of
 * merely yielding.
 *
 * Lowering priority needs no privileges; raising it would. Failures are not fatal: the app
 * simply runs at normal priority, which is a slower neighbour, not a broken one.
 */
export const BACKGROUND_PRIORITY = os.constants.priority.PRIORITY_BELOW_NORMAL

export type SetPriority = (pid: number, priority: number) => void

export function lowerPriority(
  pid: number,
  setPriority: SetPriority = os.setPriority,
  priority: number = BACKGROUND_PRIORITY,
): boolean {
  try {
    setPriority(pid, priority)
    return true
  } catch {
    return false
  }
}
