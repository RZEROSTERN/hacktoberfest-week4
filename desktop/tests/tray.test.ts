import { describe, expect, it, vi } from 'vitest'
import { type TrayActions, type TrayState, menuTemplate, statusLine } from '../src/tray'

function state(over: Partial<TrayState> = {}): TrayState {
  return { running: false, paused: false, blocker: null, lastSummary: null, ...over }
}

function actions(): TrayActions {
  return { open: vi.fn(), sortNow: vi.fn(), pause: vi.fn(), resume: vi.fn(), quit: vi.fn() }
}

function labels(state: TrayState): string[] {
  return menuTemplate(state, actions())
    .map(item => item.label)
    .filter((label): label is string => typeof label === 'string')
}

describe('statusLine', () => {
  it('says what it is doing while a run is going', () => {
    expect(statusLine(state({ running: true }))).toBe('Sorting…')
    expect(statusLine(state({ running: true, paused: true }))).toBe('Paused')
  })

  it('says what it is waiting for when it is idle', () => {
    expect(statusLine(state({ blocker: 'in-use' }))).toBe('Waiting until you step away')
    expect(statusLine(state({ blocker: 'on-battery' }))).toBe('Waiting until you plug in')
    expect(statusLine(state({ blocker: 'outside-window' }))).toBe('Waiting for the scheduled time')
  })

  it('falls back to the last result, then to a plain line', () => {
    expect(statusLine(state({ lastSummary: '12 screenshots sorted' }))).toBe(
      '12 screenshots sorted',
    )
    expect(statusLine(state())).toBe('Nothing to do yet')
  })
})

describe('menuTemplate', () => {
  it('offers Sort now whenever a run is not already going', () => {
    const idle = menuTemplate(state({ blocker: 'outside-window' }), actions())
    const sortNow = idle.find(item => item.label === 'Sort now')
    // Asking by hand outranks the schedule, so it stays available while waiting.
    expect(sortNow?.enabled).toBe(true)
  })

  it('does not offer a second run while one is going', () => {
    const running = menuTemplate(state({ running: true }), actions())
    expect(running.find(item => item.label === 'Sort now')?.enabled).toBe(false)
  })

  it('shows Pause while running and Resume once paused', () => {
    expect(labels(state({ running: true }))).toContain('Pause')
    expect(labels(state({ running: true, paused: true }))).toContain('Resume')
    expect(labels(state({ running: true, paused: true }))).not.toContain('Pause')
  })

  it('does not offer Pause when nothing is running', () => {
    const idle = menuTemplate(state(), actions())
    expect(idle.find(item => item.label === 'Pause')?.enabled).toBe(false)
  })

  it('can always be opened and quit', () => {
    expect(labels(state())).toEqual(
      expect.arrayContaining(['Open Slothshot', 'Quit']),
    )
  })

  it('wires each entry to its action', () => {
    const wired = actions()
    const menu = menuTemplate(state({ running: true }), wired)
    menu.find(item => item.label === 'Sort now')?.click?.(
      {} as never, undefined, {} as never,
    )
    expect(wired.sortNow).toHaveBeenCalled()
  })
})
