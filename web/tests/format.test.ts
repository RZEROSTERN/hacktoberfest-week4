import { describe, expect, it } from 'vitest'
import { describeRun, formatBytes, pluralize } from '~/utils/format'

describe('formatBytes', () => {
  it('keeps small sizes in bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(999)).toBe('999 B')
  })

  it('shows one decimal below ten and none above', () => {
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(1024 * 237)).toBe('237 KB')
  })

  it('climbs through the units', () => {
    expect(formatBytes(1024 ** 2 * 5)).toBe('5.0 MB')
    expect(formatBytes(1024 ** 3 * 1.4)).toBe('1.4 GB')
  })

  it('refuses nonsense rather than printing NaN', () => {
    expect(formatBytes(Number.NaN)).toBe('—')
    expect(formatBytes(-1)).toBe('—')
  })
})

describe('pluralize', () => {
  it('uses the singular for exactly one', () => {
    expect(pluralize(1, 'screenshot')).toBe('1 screenshot')
    expect(pluralize(0, 'screenshot')).toBe('0 screenshots')
    expect(pluralize(2, 'screenshot')).toBe('2 screenshots')
  })
})

describe('describeRun', () => {
  it('mentions Review only when something is waiting there', () => {
    expect(describeRun({ organized: 12, duplicates: 0, expired: 0 })).toBe(
      'Sorted 12 screenshots.'
    )
    expect(describeRun({ organized: 12, duplicates: 3, expired: 1 })).toBe(
      'Sorted 12 screenshots. 4 items waiting in Review.'
    )
  })
})
