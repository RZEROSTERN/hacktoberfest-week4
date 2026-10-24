import type { DataDirs, Layout } from './layout'

/** Only these are passed on, so a user's own OLLAMA_* or SLOTHSHOT_* settings cannot leak in. */
const PASS_THROUGH = ['PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'USER', 'LOGNAME']

/**
 * What Windows programs need to start at all: the system folder (sockets and DLL loading fail
 * without SystemRoot), the temporary folder (the api unpacks itself there), the program search
 * extensions and the processor facts the engines read. Nothing here carries a user's own settings.
 */
const WINDOWS_PASS_THROUGH = [
  'SystemRoot',
  'SystemDrive',
  'windir',
  'TEMP',
  'TMP',
  'PATHEXT',
  'COMSPEC',
  'ProgramData',
  'NUMBER_OF_PROCESSORS',
  'PROCESSOR_ARCHITECTURE',
  'USERNAME',
]

function base(source: NodeJS.ProcessEnv, platform: NodeJS.Platform): Record<string, string> {
  const env: Record<string, string> = {}
  const keys = platform === 'win32' ? [...PASS_THROUGH, ...WINDOWS_PASS_THROUGH] : PASS_THROUGH
  for (const key of keys) {
    const value = source[key]
    if (value !== undefined) env[key] = value
  }
  return env
}

export interface Ports {
  ollama: number
  api: number
}

export const APP_SCHEME = 'app'
export const APP_HOST = 'slothshot'
export const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`

/**
 * How long a model stays in memory after a request. Short on purpose: the resource budget says
 * the model is unloaded right after a run, and a run is a queue of single images, so a few
 * seconds is enough to carry it between screenshots without holding memory afterwards.
 */
export const KEEP_ALIVE = '30s'

export function ollamaUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.ollama}`
}

export function apiUrl(ports: Ports): string {
  return `http://127.0.0.1:${ports.api}`
}

/**
 * The bundled Ollama: loopback only, its own home and models folder, no cloud models, and held
 * to one model and one request at a time. The names below are the ones `ollama serve --help`
 * documents in 0.35.x.
 */
export function ollamaEnv(
  ports: Ports,
  dirs: DataDirs,
  source: NodeJS.ProcessEnv,
  platform: NodeJS.Platform = process.platform,
): Record<string, string> {
  return {
    ...base(source, platform),
    HOME: dirs.ollamaHome,
    // Ollama finds its home through USERPROFILE on Windows, so it needs the same redirect as HOME.
    ...(platform === 'win32' ? { USERPROFILE: dirs.ollamaHome } : {}),
    OLLAMA_HOST: `127.0.0.1:${ports.ollama}`,
    OLLAMA_MODELS: dirs.ollamaModels,
    OLLAMA_NO_CLOUD: '1',
    // The resource budget: one image at a time, one model resident, released quickly.
    OLLAMA_MAX_LOADED_MODELS: '1',
    OLLAMA_NUM_PARALLEL: '1',
    OLLAMA_KEEP_ALIVE: KEEP_ALIVE,
  }
}

export function apiEnv(
  ports: Ports,
  dirs: DataDirs,
  _layout: Layout,
  parentPid: number,
  source: NodeJS.ProcessEnv,
  platform: NodeJS.Platform = process.platform,
): Record<string, string> {
  return {
    ...base(source, platform),
    SLOTHSHOT_HOST: '127.0.0.1',
    SLOTHSHOT_PORT: String(ports.api),
    SLOTHSHOT_OLLAMA_URL: ollamaUrl(ports),
    SLOTHSHOT_DATA_DIR: dirs.data,
    SLOTHSHOT_MODELS_DIR: dirs.models,
    SLOTHSHOT_CORS_ORIGINS: JSON.stringify([APP_ORIGIN]),
    SLOTHSHOT_PARENT_PID: String(parentPid),
  }
}
