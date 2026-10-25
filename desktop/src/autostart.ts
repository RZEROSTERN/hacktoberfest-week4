/**
 * Starting at login, which is three different things on three platforms.
 *
 * Electron's `setLoginItemSettings` is documented for macOS and Windows only, so Linux is
 * handled here directly with an XDG autostart entry, which is the freedesktop convention the
 * major desktops follow.
 *
 * On macOS the same docs note that login items want a signed and notarized app. Slothshot is
 * ad-hoc signed, so this may silently not take effect there; the UI reads the setting back
 * rather than assuming it was applied.
 */

import path from 'node:path'

export type Strategy = 'electron' | 'xdg'

export function strategyFor(platform: NodeJS.Platform = process.platform): Strategy {
  return platform === 'linux' ? 'xdg' : 'electron'
}

export function autostartFile(home: string, configHome?: string): string {
  const base = configHome && configHome.length > 0 ? configHome : path.join(home, '.config')
  return path.join(base, 'autostart', 'slothshot.desktop')
}

/** An XDG autostart entry. `Hidden=true` is how the spec says to disable one. */
export function desktopEntry(execPath: string, enabled: boolean): string {
  return [
    '[Desktop Entry]',
    'Type=Application',
    'Name=Slothshot',
    'Comment=Sorts your screenshots while you are not using your computer',
    `Exec=${execPath} --background`,
    'Terminal=false',
    'X-GNOME-Autostart-enabled=true',
    `Hidden=${enabled ? 'false' : 'true'}`,
    '',
  ].join('\n')
}

export interface AutostartHost {
  setLoginItemSettings: (settings: { openAtLogin: boolean }) => void
  getLoginItemSettings: () => { openAtLogin: boolean }
  writeFile: (file: string, contents: string) => void
  removeFile: (file: string) => void
  fileExists: (file: string) => boolean
  execPath: string
  home: string
  configHome?: string
}

/**
 * Turn start-at-login on or off, and report what actually happened.
 *
 * The return value is read back rather than assumed: Electron's own docs note that login items
 * want a signed and notarized app on macOS, and Slothshot is ad-hoc signed, so the request can
 * quietly not take effect there. The settings screen shows the value this returns.
 */
export function applyAutostart(
  enabled: boolean,
  host: AutostartHost,
  platform: NodeJS.Platform = process.platform,
): boolean {
  if (strategyFor(platform) === 'xdg') {
    const file = autostartFile(host.home, host.configHome)
    if (enabled) {
      host.writeFile(file, desktopEntry(host.execPath, true))
      return host.fileExists(file)
    }
    host.removeFile(file)
    return false
  }

  host.setLoginItemSettings({ openAtLogin: enabled })
  return host.getLoginItemSettings().openAtLogin
}
