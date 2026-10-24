import fs from 'node:fs'
import path from 'node:path'
import { BrowserWindow, app, net, protocol, shell } from 'electron'

import { APP_HOST, APP_ORIGIN, APP_SCHEME } from './env'
import { dataDirs, layout } from './layout'
import { isAllowedExternal, isAllowedRequest } from './security'

// Development: `npm run dev` serves the Nuxt app and the api itself, so the shell points at them
// instead of the bundled copies. Unset in a packaged build.
const DEV_URL = process.env.SLOTHSHOT_DEV_URL
const DEV_API = process.env.SLOTHSHOT_DEV_API

// The custom scheme has to be declared before the app is ready.
protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
  },
])

let mainWindow: BrowserWindow | null = null

/** Serves the generated SPA from the resources folder, refusing anything outside it. */
function registerAppProtocol(webRoot: string): void {
  protocol.handle(APP_SCHEME, request => {
    const { pathname } = new URL(request.url)
    const relative = pathname === '/' ? 'index.html' : pathname.slice(1)
    const target = path.join(webRoot, relative)

    // A request like app://slothshot/../../etc/passwd must not escape the web root.
    const resolved = path.resolve(target)
    if (resolved !== path.resolve(webRoot) && !resolved.startsWith(path.resolve(webRoot) + path.sep)) {
      return new Response('Forbidden', { status: 403 })
    }
    // Unknown paths fall back to the SPA entry so client-side routing works on reload.
    const file = fs.existsSync(resolved) && fs.statSync(resolved).isFile()
      ? resolved
      : path.join(webRoot, 'index.html')
    return net.fetch(`file://${file}`)
  })
}

function createWindow(apiOrigin: string): BrowserWindow {
  const window = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 720,
    minHeight: 520,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webviewTag: false,
      additionalArguments: [`--slothshot-api-base=${apiOrigin}`],
    },
  })

  // Nothing navigates away from the app's own pages, and nothing opens a second window.
  window.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedRequest(url, apiOrigin)) event.preventDefault()
  })
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedExternal(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => {
    callback(false) // the app needs no camera, microphone, location or notifications permission prompt
  })

  window.once('ready-to-show', () => window.show())
  return window
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  void app.whenReady().then(() => {
    const dirs = dataDirs(app.getPath('userData'))
    for (const dir of Object.values(dirs)) fs.mkdirSync(dir, { recursive: true })

    const resources = process.resourcesPath
    const paths = layout(resources)
    const apiOrigin = DEV_API ?? 'http://127.0.0.1:8765'

    if (!DEV_URL) registerAppProtocol(paths.webRoot)

    mainWindow = createWindow(apiOrigin)
    void mainWindow.loadURL(DEV_URL ?? `${APP_ORIGIN}/`)
    mainWindow.on('closed', () => {
      mainWindow = null
    })
  })

  app.on('window-all-closed', () => {
    // The tray app in step 7 keeps running here; for now the shell follows the platform default.
    if (process.platform !== 'darwin') app.quit()
  })

  app.on('activate', () => {
    if (mainWindow === null && app.isReady()) {
      mainWindow = createWindow(DEV_API ?? 'http://127.0.0.1:8765')
      void mainWindow.loadURL(DEV_URL ?? `${APP_ORIGIN}/`)
    }
  })
}

export { APP_HOST }
