/** Minimal API exposed by the desktop preload via contextBridge (absent in a plain browser). */
interface DesktopBridge {
  apiBase: string
}

interface Window {
  desktop?: DesktopBridge
}
