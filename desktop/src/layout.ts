import path from 'node:path'

/** Folders the app writes to, all inside the user's own data directory. */
export interface DataDirs {
  data: string // SQLite index and journal
  models: string // downloaded model metadata
  ollamaHome: string // the bundled Ollama's HOME, kept away from a system-wide one
  ollamaModels: string // where model weights land
}

/** Bundled programs, resolved against the packaged resources folder. */
export interface Layout {
  ollamaBinary: string
  apiBinary: string
  webRoot: string
  programsDir: string // everything bundled lives under here; the Windows sweep matches on it
}

export function dataDirs(userData: string): DataDirs {
  return {
    data: path.join(userData, 'data'),
    models: path.join(userData, 'models'),
    ollamaHome: path.join(userData, 'ollama-home'),
    ollamaModels: path.join(userData, 'ollama-models'),
  }
}

export function layout(resources: string, platform: NodeJS.Platform = process.platform): Layout {
  const exe = platform === 'win32' ? '.exe' : ''
  return {
    ollamaBinary: path.join(resources, 'ollama', `ollama${exe}`),
    apiBinary: path.join(resources, 'api', `slothshot-api${exe}`),
    webRoot: path.join(resources, 'web'),
    programsDir: resources,
  }
}
