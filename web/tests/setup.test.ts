import { describe, expect, it } from 'vitest'
import type { RecommendedModel, SetupProgress, SetupStep } from '~/types/api'
import { canResume, downloadLine, formatEta, formatSpeed, modelCost } from '~/utils/setup'

function step(over: Partial<SetupStep> = {}): SetupStep {
  return {
    id: 'model',
    label: 'Downloading the model',
    state: 'running',
    detail: 'qwen3-vl:2b-instruct',
    skipped: false,
    completed: 0,
    total: 0,
    speed_bps: null,
    eta_s: null,
    ...over,
  }
}

function progress(over: Partial<SetupProgress> = {}): SetupProgress {
  return {
    state: 'idle',
    model: null,
    steps: [step()],
    error_code: null,
    overall: { fraction: 0, completed_bytes: 0, total_bytes: 0 },
    ...over,
  }
}

describe('formatSpeed', () => {
  it('reads as a rate', () => {
    // formatBytes keeps a decimal below ten and drops it above, so this reads "12 MB/s".
    expect(formatSpeed(12_400_000)).toBe('12 MB/s')
    expect(formatSpeed(5_200_000)).toBe('5.0 MB/s')
  })

  it('is absent before there is anything to measure', () => {
    expect(formatSpeed(null)).toBeNull()
    expect(formatSpeed(0)).toBeNull()
  })
})

describe('formatEta', () => {
  it('stays vague on purpose', () => {
    // A precise wrong number is worse than a rough one.
    expect(formatEta(30)).toBe('less than a minute left')
    expect(formatEta(60)).toBe('about 1 minute left')
    expect(formatEta(250)).toBe('about 4 minutes left')
    expect(formatEta(7200)).toBe('about 2 hours left')
  })

  it('says nothing rather than something wrong', () => {
    expect(formatEta(null)).toBeNull()
    expect(formatEta(0)).toBeNull()
    expect(formatEta(Number.POSITIVE_INFINITY)).toBeNull()
  })
})

describe('downloadLine', () => {
  it('says how much of how much, how fast and how long', () => {
    const line = downloadLine(step({ completed: 500_000_000, total: 1_900_000_000, speed_bps: 12_400_000, eta_s: 113 }))
    expect(line).toBe('477 MB of 1.8 GB · 12 MB/s · about 2 minutes left')
  })

  it('drops the parts it cannot know yet', () => {
    expect(downloadLine(step({ completed: 1000, total: 2000 }))).toBe('1000 B of 2.0 KB')
  })

  it('is absent when nothing is downloading', () => {
    expect(downloadLine(step({ state: 'pending' }))).toBeNull()
    expect(downloadLine(step({ state: 'done', total: 0 }))).toBeNull()
  })
})

describe('modelCost', () => {
  const model: RecommendedModel = {
    model: 'qwen3-vl:2b-instruct',
    title: 'Qwen3-VL 2B Instruct',
    recommended: true,
    size_bytes: 1_900_000_000,
    size_exact: false,
    ram_gb: 8,
    max_image_px: 768,
    license: 'Apache 2.0',
    note: 'The default.',
  }

  it('states size, memory and license before anything is downloaded', () => {
    expect(modelCost(model)).toBe('about 1.8 GB to download · needs 8 GB of memory · Apache 2.0')
  })

  it('drops the hedge when the size is exact', () => {
    expect(modelCost({ ...model, size_exact: true })).toContain('1.8 GB to download')
    expect(modelCost({ ...model, size_exact: true })).not.toContain('about')
  })
})

describe('canResume', () => {
  it('offers to continue only when something was actually downloaded', () => {
    const partial = { ...step(), completed: 5_000_000 }
    expect(canResume(progress({ state: 'paused', model: 'm:1', steps: [partial] }))).toBe(true)
    expect(canResume(progress({ state: 'paused', model: 'm:1' }))).toBe(false)
    expect(canResume(progress({ state: 'done', model: 'm:1', steps: [partial] }))).toBe(false)
  })

  it('offers to continue after the app was closed mid-download', () => {
    const partial = { ...step(), completed: 5_000_000 }
    expect(canResume(progress({ state: 'interrupted', model: 'm:1', steps: [partial] }))).toBe(true)
  })
})
