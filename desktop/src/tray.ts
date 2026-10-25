/**
 * The menu bar item.
 *
 * The menu template is built by a pure function so its wording and its enabled/disabled states
 * can be tested without an Electron window. What the tray says is the only feedback a user
 * gets while the app is doing nothing visible, so it has to be accurate about why.
 */

import type { MenuItemConstructorOptions } from 'electron'
import { type Blocker, explain } from './schedule'

export interface TrayState {
  running: boolean
  paused: boolean
  blocker: Blocker | null
  lastSummary: string | null
}

/** The single line under the app name. Says what it is doing, or what it is waiting for. */
export function statusLine(state: TrayState): string {
  if (state.running) return state.paused ? 'Paused' : 'Sorting…'
  if (state.blocker) return explain(state.blocker)
  return state.lastSummary ?? 'Nothing to do yet'
}

export interface TrayActions {
  open: () => void
  sortNow: () => void
  pause: () => void
  resume: () => void
  quit: () => void
}

export function menuTemplate(state: TrayState, actions: TrayActions): MenuItemConstructorOptions[] {
  return [
    { label: `Slothshot — ${statusLine(state)}`, enabled: false },
    { type: 'separator' },
    { label: 'Open Slothshot', click: actions.open },
    {
      label: 'Sort now',
      // Starting a run by hand is a clear instruction, so it is offered whenever one is not
      // already going, whatever the schedule would have decided.
      enabled: !state.running,
      click: actions.sortNow,
    },
    state.paused
      ? { label: 'Resume', enabled: state.running, click: actions.resume }
      : { label: 'Pause', enabled: state.running, click: actions.pause },
    { type: 'separator' },
    { label: 'Quit', click: actions.quit },
  ]
}
