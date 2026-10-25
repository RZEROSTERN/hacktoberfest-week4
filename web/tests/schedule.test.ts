import { describe, expect, it } from 'vitest'
import type { Schedule } from '~/types/api'
import { describeSchedule, spansMidnight } from '~/utils/schedule'

function schedule(over: Partial<Schedule> = {}): Schedule {
  return {
    enabled: true,
    windowStart: '23:00',
    windowEnd: '07:00',
    requireIdle: true,
    idleThresholdSeconds: 300,
    pauseOnBattery: true,
    ...over,
  }
}

describe('describeSchedule', () => {
  it('describes the default in one sentence', () => {
    expect(describeSchedule(schedule())).toBe(
      'Sorts between 23:00 and 07:00, but only while you are away from the computer and while it is plugged in.',
    )
  })

  it('drops the guards the user turned off', () => {
    expect(describeSchedule(schedule({ pauseOnBattery: false }))).toBe(
      'Sorts between 23:00 and 07:00, but only while you are away from the computer.',
    )
    expect(describeSchedule(schedule({ requireIdle: false, pauseOnBattery: false }))).toBe(
      'Sorts between 23:00 and 07:00.',
    )
  })

  it('says plainly when scheduling is off, and that manual sorting still works', () => {
    const line = describeSchedule(schedule({ enabled: false }))
    expect(line).toContain('off')
    expect(line).toContain('still sort')
  })
})

describe('spansMidnight', () => {
  it('recognises an overnight window', () => {
    expect(spansMidnight(schedule())).toBe(true)
    expect(spansMidnight(schedule({ windowStart: '09:00', windowEnd: '17:00' }))).toBe(false)
  })
})
