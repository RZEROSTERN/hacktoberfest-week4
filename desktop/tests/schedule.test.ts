import { describe, expect, it } from 'vitest'
import {
  type Conditions,
  DEFAULT_SCHEDULE,
  type Schedule,
  explain,
  inWindow,
  minutesOf,
  shouldRun,
} from '../src/schedule'

function at(hour: number, minute = 0): Date {
  return new Date(2026, 9, 25, hour, minute)
}

function schedule(over: Partial<Schedule> = {}): Schedule {
  return { ...DEFAULT_SCHEDULE, ...over }
}

function conditions(over: Partial<Conditions> = {}): Conditions {
  return { now: at(2), idleSeconds: 9_999, onBattery: false, ...over }
}

describe('minutesOf', () => {
  it('reads a wall-clock time', () => {
    expect(minutesOf('00:00')).toBe(0)
    expect(minutesOf('07:30')).toBe(450)
    expect(minutesOf('23:59')).toBe(1439)
  })

  it('refuses nonsense rather than guessing', () => {
    expect(minutesOf('24:00')).toBeNull()
    expect(minutesOf('07:60')).toBeNull()
    expect(minutesOf('7pm')).toBeNull()
    expect(minutesOf('')).toBeNull()
  })
})

describe('inWindow across midnight', () => {
  // The default window is 23:00 to 07:00, which is the case most likely to be got wrong.
  it.each([
    [23, true],
    [0, true],
    [2, true],
    [6, true],
    [7, false], // the end is exclusive
    [12, false],
    [22, false],
  ])('at %i:00 -> %s', (hour, expected) => {
    expect(inWindow(at(hour), '23:00', '07:00')).toBe(expected)
  })
})

describe('inWindow within one day', () => {
  it.each([
    [8, false],
    [9, true],
    [16, true],
    [17, false],
  ])('at %i:00 -> %s', (hour, expected) => {
    expect(inWindow(at(hour), '09:00', '17:00')).toBe(expected)
  })

  it('treats a zero-length window as any time', () => {
    expect(inWindow(at(3), '00:00', '00:00')).toBe(true)
    expect(inWindow(at(15), '00:00', '00:00')).toBe(true)
  })

  it('refuses a window it cannot read', () => {
    expect(inWindow(at(3), 'midnight', '07:00')).toBe(false)
  })
})

describe('shouldRun', () => {
  it('runs when everything lines up', () => {
    expect(shouldRun(schedule(), conditions())).toEqual({ run: true })
  })

  it('does nothing when scheduled sorting is off', () => {
    expect(shouldRun(schedule({ enabled: false }), conditions())).toEqual({
      run: false,
      because: 'disabled',
    })
  })

  it('waits for the window', () => {
    expect(shouldRun(schedule(), conditions({ now: at(15) }))).toEqual({
      run: false,
      because: 'outside-window',
    })
  })

  it('waits while the computer is in use', () => {
    expect(shouldRun(schedule(), conditions({ idleSeconds: 10 }))).toEqual({
      run: false,
      because: 'in-use',
    })
  })

  it('waits while on battery', () => {
    expect(shouldRun(schedule(), conditions({ onBattery: true }))).toEqual({
      run: false,
      because: 'on-battery',
    })
  })

  it('reports battery before idleness, because that is the one the user can act on', () => {
    const blocked = shouldRun(schedule(), conditions({ onBattery: true, idleSeconds: 0 }))
    expect(blocked).toEqual({ run: false, because: 'on-battery' })
  })

  it('honours a user who turned the checks off', () => {
    const relaxed = schedule({ requireIdle: false, pauseOnBattery: false })
    expect(shouldRun(relaxed, conditions({ idleSeconds: 0, onBattery: true }))).toEqual({
      run: true,
    })
  })

  it('uses the idle threshold it was given', () => {
    const impatient = schedule({ idleThresholdSeconds: 5 })
    expect(shouldRun(impatient, conditions({ idleSeconds: 10 }))).toEqual({ run: true })
    expect(shouldRun(impatient, conditions({ idleSeconds: 4 }))).toEqual({
      run: false,
      because: 'in-use',
    })
  })
})

describe('explain', () => {
  it('never blames the user for using their own computer', () => {
    expect(explain('in-use')).toBe('Waiting until you step away')
    expect(explain('on-battery')).toBe('Waiting until you plug in')
    for (const blocker of ['disabled', 'outside-window', 'in-use', 'on-battery'] as const) {
      expect(explain(blocker)).not.toMatch(/error|fail|cannot|refus/i)
    }
  })
})
