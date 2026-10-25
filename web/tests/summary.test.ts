import { describe, expect, it } from 'vitest'
import type { Summary } from '~/types/api'
import { headline, reclaimLine, reviewLine, skippedLine } from '~/utils/summary'

function summary(over: Partial<Summary> = {}): Summary {
  return {
    run_id: 1,
    finished_at: '2026-10-24T06:00:00Z',
    sorted_count: 0,
    skipped_count: 0,
    duplicates_waiting: 0,
    expired_waiting: 0,
    reclaimable_bytes: 0,
    total_indexed: 0,
    ...over,
  }
}

describe('headline', () => {
  it('says so plainly before the first run', () => {
    expect(headline(summary({ run_id: null }))).toBe('Nothing sorted yet.')
  })

  it('distinguishes a quiet night from no night at all', () => {
    expect(headline(summary({ sorted_count: 0 }))).toBe('Nothing new to sort.')
    expect(headline(summary({ sorted_count: 1 }))).toBe('Sorted 1 screenshot.')
    expect(headline(summary({ sorted_count: 14 }))).toBe('Sorted 14 screenshots.')
  })
})

describe('reviewLine', () => {
  it('is absent when nothing is waiting', () => {
    expect(reviewLine(summary())).toBeNull()
  })

  it('names only the kinds that are actually there', () => {
    expect(reviewLine(summary({ duplicates_waiting: 3 }))).toBe('3 duplicates waiting in Review.')
    expect(reviewLine(summary({ expired_waiting: 2 }))).toBe('2 expired waiting in Review.')
    expect(reviewLine(summary({ duplicates_waiting: 1, expired_waiting: 2 })))
      .toBe('1 duplicate and 2 expired waiting in Review.')
  })
})

describe('reclaimLine', () => {
  it('is information, not an offer: the app never deletes anything', () => {
    const line = reclaimLine(summary({ reclaimable_bytes: 1024 * 1024 * 237 }))
    expect(line).toBe('Deleting them yourself would free 237 MB.')
    expect(line).not.toMatch(/delete (them|now)\b/i)
  })

  it('is absent when there is nothing to reclaim', () => {
    expect(reclaimLine(summary())).toBeNull()
  })
})

describe('skippedLine', () => {
  it('mentions unreadable files without blaming the user', () => {
    expect(skippedLine(summary({ skipped_count: 1 })))
      .toBe('1 screenshot could not be read and was left alone.')
    expect(skippedLine(summary({ skipped_count: 3 })))
      .toBe('3 screenshots could not be read and were left alone.')
  })

  it('is absent when nothing was skipped', () => {
    expect(skippedLine(summary())).toBeNull()
  })
})
