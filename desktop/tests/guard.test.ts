import { describe, expect, it, vi } from 'vitest'
import { type Api, type Machine, tick } from '../src/guard'
import { DEFAULT_SCHEDULE, type Schedule } from '../src/schedule'

function api(over: Partial<Api> & { schedule?: Schedule; paused?: boolean; running?: boolean } = {}) {
  const base: Api = {
    settings: async () => ({
      schedule: over.schedule ?? DEFAULT_SCHEDULE,
      paused: over.paused ?? false,
    }),
    currentRun: async () => (over.running ? { id: 1, status: 'analyzing' } : null),
    start: vi.fn(async () => {}),
    pause: vi.fn(async () => {}),
    resume: vi.fn(async () => {}),
  }
  return { ...base, ...over } as Api
}

function machine(over: Partial<Machine> = {}): Machine {
  return {
    now: () => new Date(2026, 9, 25, 2, 0), // inside the default overnight window
    idleSeconds: () => 9_999,
    onBattery: () => false,
    ...over,
  }
}

describe('tick', () => {
  it('starts a run when the conditions allow it', async () => {
    const a = api()
    const result = await tick(a, machine())
    expect(result.started).toBe(true)
    expect(a.start).toHaveBeenCalled()
  })

  it('does not start outside the window', async () => {
    const a = api()
    const result = await tick(a, machine({ now: () => new Date(2026, 9, 25, 15, 0) }))
    expect(result.started).toBeUndefined()
    expect(result.blocker).toBe('outside-window')
    expect(a.start).not.toHaveBeenCalled()
  })

  it('does not start while someone is using the computer', async () => {
    const a = api()
    const result = await tick(a, machine({ idleSeconds: () => 5 }))
    expect(result.blocker).toBe('in-use')
    expect(a.start).not.toHaveBeenCalled()
  })

  it('does not start a second run while one is going', async () => {
    const a = api({ running: true })
    await tick(a, machine())
    expect(a.start).not.toHaveBeenCalled()
  })

  it('pauses a run in flight the moment the user comes back', async () => {
    const a = api({ running: true })
    const result = await tick(a, machine({ idleSeconds: () => 2 }))
    expect(result.paused).toBe(true)
    expect(a.pause).toHaveBeenCalled()
  })

  it('pauses a run in flight when the machine goes on battery', async () => {
    const a = api({ running: true })
    const result = await tick(a, machine({ onBattery: () => true }))
    expect(result.paused).toBe(true)
    expect(a.pause).toHaveBeenCalled()
  })

  it('resumes once the conditions allow it again', async () => {
    const a = api({ running: true, paused: true })
    const result = await tick(a, machine())
    expect(result.resumed).toBe(true)
    expect(a.resume).toHaveBeenCalled()
  })

  it('does not pause a run that is already paused', async () => {
    const a = api({ running: true, paused: true })
    await tick(a, machine({ idleSeconds: () => 1 }))
    expect(a.pause).not.toHaveBeenCalled()
  })

  it('stays out of the way entirely when scheduling is off', async () => {
    const a = api({ schedule: { ...DEFAULT_SCHEDULE, enabled: false } })
    const result = await tick(a, machine())
    expect(result.blocker).toBe('disabled')
    expect(a.start).not.toHaveBeenCalled()
  })
})
