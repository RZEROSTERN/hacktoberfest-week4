import { describe, expect, it } from 'vitest'
import { RunAnnouncer, type Summary, notificationFor } from '../src/notify'

function summary(over: Partial<Summary> = {}): Summary {
  return {
    run_id: 1,
    sorted_count: 0,
    skipped_count: 0,
    duplicates_waiting: 0,
    expired_waiting: 0,
    reclaimable_bytes: 0,
    total_indexed: 0,
    ...over,
  }
}

describe('notificationFor', () => {
  it('says what happened, in counts only', () => {
    expect(notificationFor(summary({ sorted_count: 12 }))).toEqual({
      title: 'Slothshot',
      body: '12 screenshots sorted.',
    })
  })

  it('mentions Review when something is waiting there', () => {
    const got = notificationFor(summary({ sorted_count: 12, duplicates_waiting: 3, expired_waiting: 1 }))
    expect(got?.body).toBe('12 screenshots sorted. 4 items waiting in Review.')
  })

  it('gets the singular right', () => {
    const got = notificationFor(summary({ sorted_count: 1, duplicates_waiting: 1 }))
    expect(got?.body).toBe('1 screenshot sorted. 1 item waiting in Review.')
  })

  it('stays quiet about a run that did nothing', () => {
    // An overnight app that reports having nothing to do becomes intolerable.
    expect(notificationFor(summary({ sorted_count: 0 }))).toBeNull()
  })

  it('stays quiet before any run has happened', () => {
    expect(notificationFor(summary({ run_id: null, sorted_count: 5 }))).toBeNull()
  })

  it('never names a file or says what a screenshot contains', () => {
    const got = notificationFor(summary({ sorted_count: 3, duplicates_waiting: 1 }))
    expect(got?.body).toMatch(/^[\d\s\w.]+$/)
    expect(got?.body).not.toMatch(/\.(png|jpe?g|webp)/i)
    expect(got?.body).not.toMatch(/\//)
  })
})

describe('RunAnnouncer', () => {
  it('announces a finished run once', () => {
    const announcer = new RunAnnouncer()
    const finished = summary({ run_id: 7, sorted_count: 4 })
    expect(announcer.consider(finished)?.body).toBe('4 screenshots sorted.')
    expect(announcer.consider(finished)).toBeNull()
  })

  it('announces the next run too', () => {
    const announcer = new RunAnnouncer()
    announcer.consider(summary({ run_id: 7, sorted_count: 4 }))
    expect(announcer.consider(summary({ run_id: 8, sorted_count: 2 }))?.body)
      .toBe('2 screenshots sorted.')
  })

  it('does not reconsider a quiet run later', () => {
    const announcer = new RunAnnouncer()
    expect(announcer.consider(summary({ run_id: 7, sorted_count: 0 }))).toBeNull()
    // Same run, now seen with counts filled in by a later poll: still not news.
    expect(announcer.consider(summary({ run_id: 7, sorted_count: 4 }))).toBeNull()
  })
})
