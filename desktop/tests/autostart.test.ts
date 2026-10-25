import { describe, expect, it, vi } from 'vitest'
import { applyAutostart, autostartFile, desktopEntry, strategyFor } from '../src/autostart'

describe('strategyFor', () => {
  it('uses Electron where Electron supports it, and XDG on Linux', () => {
    // setLoginItemSettings is documented for macOS and Windows only.
    expect(strategyFor('darwin')).toBe('electron')
    expect(strategyFor('win32')).toBe('electron')
    expect(strategyFor('linux')).toBe('xdg')
  })
})

describe('autostartFile', () => {
  it('follows XDG_CONFIG_HOME when it is set', () => {
    expect(autostartFile('/home/x', '/home/x/.myconfig')).toBe(
      '/home/x/.myconfig/autostart/slothshot.desktop',
    )
  })

  it('falls back to ~/.config', () => {
    expect(autostartFile('/home/x')).toBe('/home/x/.config/autostart/slothshot.desktop')
    expect(autostartFile('/home/x', '')).toBe('/home/x/.config/autostart/slothshot.desktop')
  })
})

describe('desktopEntry', () => {
  it('is a valid entry pointing at the app', () => {
    const entry = desktopEntry('/opt/slothshot/slothshot', true)
    expect(entry.startsWith('[Desktop Entry]')).toBe(true)
    expect(entry).toContain('Type=Application')
    expect(entry).toContain('Exec=/opt/slothshot/slothshot --background')
    expect(entry).toContain('Hidden=false')
  })

  it('disables itself with Hidden, which is how the spec turns one off', () => {
    expect(desktopEntry('/opt/slothshot/slothshot', false)).toContain('Hidden=true')
  })
})

describe('applyAutostart', () => {
  function host(over: Partial<import('../src/autostart').AutostartHost> = {}) {
    const written = new Map<string, string>()
    return {
      written,
      host: {
        setLoginItemSettings: vi.fn(),
        getLoginItemSettings: vi.fn(() => ({ openAtLogin: true })),
        writeFile: vi.fn((f: string, c: string) => void written.set(f, c)),
        removeFile: vi.fn((f: string) => void written.delete(f)),
        fileExists: vi.fn((f: string) => written.has(f)),
        execPath: '/opt/slothshot/slothshot',
        home: '/home/x',
        ...over,
      },
    }
  }

  it('writes an XDG entry on Linux', () => {
    const { host: h, written } = host()
    expect(applyAutostart(true, h, 'linux')).toBe(true)
    expect(written.get('/home/x/.config/autostart/slothshot.desktop')).toContain(
      'Exec=/opt/slothshot/slothshot --background',
    )
    expect(h.setLoginItemSettings).not.toHaveBeenCalled()
  })

  it('removes the XDG entry when turned off', () => {
    const { host: h, written } = host()
    applyAutostart(true, h, 'linux')
    expect(applyAutostart(false, h, 'linux')).toBe(false)
    expect(written.size).toBe(0)
  })

  it('asks Electron on macOS and Windows', () => {
    const { host: h } = host()
    expect(applyAutostart(true, h, 'darwin')).toBe(true)
    expect(h.setLoginItemSettings).toHaveBeenCalledWith({ openAtLogin: true })
  })

  it('reports what actually took effect, not what was asked for', () => {
    // An ad-hoc signed app on macOS can have the request quietly ignored.
    const { host: h } = host({ getLoginItemSettings: vi.fn(() => ({ openAtLogin: false })) })
    expect(applyAutostart(true, h, 'darwin')).toBe(false)
  })
})
