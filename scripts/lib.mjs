// Shared helpers for the build scripts. Plain Node (22 or newer), no dependencies, so the same code runs
// on macOS, Windows and Linux, in CI and on a developer's machine.
import { spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const versions = JSON.parse(fs.readFileSync(path.join(root, 'scripts', 'versions.json'), 'utf8'))
export const buildDir = path.join(root, 'desktop', 'build')
export const downloadsDir = path.join(root, '.dev', 'downloads')

const SUPPORTED = ['darwin-arm64', 'win32-x64', 'linux-x64']

/** The system this runs on, as one of the three that are built: darwin-arm64, win32-x64 or linux-x64. */
export function platformId(platform = process.platform, arch = process.arch) {
  const id = `${platform}-${arch}`
  if (!SUPPORTED.includes(id)) {
    throw new Error(`${id} is not a supported build system (supported: ${SUPPORTED.join(', ')})`)
  }
  return id
}

/** Where each bundled program sits inside its folder, per system. Mirrors desktop/src/layout.ts. */
export function programPaths(id = platformId()) {
  const exe = id.startsWith('win32') ? '.exe' : ''
  return {
    // The Linux archive keeps Ollama under bin/; the others put it at the top.
    ollama: id.startsWith('linux') ? ['ollama', 'bin', 'ollama'] : ['ollama', `ollama${exe}`],
    api: ['api', `slothshot-api${exe}`],
  }
}

/**
 * The tar to use. On Windows, Git Bash puts GNU tar first on the PATH; it reads `D:\\file` as a file on a host
 * called D and cannot open zip files. Windows 10 and later ship bsdtar, which does both.
 */
export function tarProgram() {
  if (process.platform !== 'win32') return 'tar'
  return path.join(process.env.SystemRoot ?? 'C:\\Windows', 'System32', 'tar.exe')
}

/** The resources folder inside the app electron-builder leaves unpacked, per system (what CI smoke-tests). */
export function packagedResources(id = platformId()) {
  return {
    'darwin-arm64': 'desktop/release/mac-arm64/Slothshot.app/Contents/Resources',
    'win32-x64': 'desktop/release/win-unpacked/resources',
    'linux-x64': 'desktop/release/linux-unpacked/resources',
  }[id]
}

export function formatBytes(bytes) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(2)} GB`
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`
  return `${bytes} B`
}

/** Prints a line that GitHub Actions folds into a collapsible group; plain text elsewhere. */
export function group(title) {
  console.log(process.env.GITHUB_ACTIONS ? `::group::${title}` : `\n== ${title}`)
}
export function endGroup() {
  if (process.env.GITHUB_ACTIONS) console.log('::endgroup::')
}

/** Runs a program, shows its output and throws if it fails. */
export function run(command, args = [], options = {}) {
  console.log(`$ ${[command, ...args].map(a => (/\s/.test(a) ? JSON.stringify(a) : a)).join(' ')}`)
  const result = spawnSync(command, args, { stdio: 'inherit', ...options })
  if (result.error) throw new Error(`${command} could not be started: ${result.error.message}`)
  if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.signal})`)
}

/** Like run, but returns what the program printed. */
export function capture(command, args = [], options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', ...options })
  if (result.error) throw new Error(`${command} could not be started: ${result.error.message}`)
  return { status: result.status, stdout: result.stdout ?? '', stderr: result.stderr ?? '' }
}

export function sha256File(file) {
  const hash = crypto.createHash('sha256')
  const fd = fs.openSync(file, 'r')
  try {
    const buffer = Buffer.alloc(1 << 20)
    for (let n = fs.readSync(fd, buffer, 0, buffer.length, null); n > 0; n = fs.readSync(fd, buffer, 0, buffer.length, null)) {
      hash.update(buffer.subarray(0, n))
    }
  } finally {
    fs.closeSync(fd)
  }
  return hash.digest('hex')
}

/**
 * Downloads `url` to `dest` unless a file with the expected SHA-256 is already there. The checksum is
 * always checked, and a download that does not match is deleted, never kept.
 */
export async function download(url, dest, sha256) {
  if (fs.existsSync(dest) && sha256File(dest) === sha256) {
    console.log(`already downloaded and verified: ${path.basename(dest)}`)
    return dest
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  const part = `${dest}.part`
  let lastError
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      console.log(`downloading ${url} (attempt ${attempt})`)
      const response = await fetch(url, { redirect: 'follow' })
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)
      const out = fs.createWriteStream(part)
      const reader = response.body.getReader()
      for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
        if (!out.write(chunk.value)) await new Promise(resolve => out.once('drain', resolve))
      }
      await new Promise((resolve, reject) => out.end(err => (err ? reject(err) : resolve())))
      const actual = sha256File(part)
      if (actual !== sha256) {
        fs.rmSync(part, { force: true })
        throw new Error(`checksum mismatch for ${path.basename(dest)}: expected ${sha256}, got ${actual}`)
      }
      fs.renameSync(part, dest)
      return dest
    } catch (error) {
      lastError = error
      fs.rmSync(part, { force: true })
      if (String(error.message).includes('checksum mismatch')) break // retrying would give the same file
      await new Promise(resolve => setTimeout(resolve, attempt * 2000))
    }
  }
  throw lastError
}

/** Total size in bytes of a folder or file. */
export function sizeOf(target) {
  const stat = fs.lstatSync(target)
  if (!stat.isDirectory()) return stat.size
  return fs.readdirSync(target).reduce((sum, name) => sum + sizeOf(path.join(target, name)), 0)
}

export function rmrf(target) {
  fs.rmSync(target, { recursive: true, force: true })
}

export function mkdirp(target) {
  fs.mkdirSync(target, { recursive: true })
}

/** A short note saying what a folder was built from, so an unchanged input skips the rebuild. */
export function stampMatches(dir, inputs) {
  try {
    return fs.readFileSync(path.join(dir, '.stamp'), 'utf8') === JSON.stringify(inputs)
  } catch {
    return false
  }
}
export function writeStamp(dir, inputs) {
  fs.writeFileSync(path.join(dir, '.stamp'), JSON.stringify(inputs))
}

/** The first executable found for a name, or null. */
export function which(name) {
  const lookup = process.platform === 'win32' ? 'where' : 'which'
  const { status, stdout } = capture(lookup, [name])
  return status === 0 ? stdout.split(/\r?\n/)[0].trim() : null
}
