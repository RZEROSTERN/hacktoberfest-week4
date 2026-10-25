// Builds the installer for the system this runs on with electron-builder, from what the other scripts left in
// desktop/build and web/.output. macOS: .dmg (arm64). Windows: NSIS .exe (x64). Linux: AppImage and .deb (x64).
import fs from 'node:fs'
import path from 'node:path'
import { endGroup, group, platformId, programPaths, buildDir, root, run } from './lib.mjs'

const id = platformId()
const desktop = path.join(root, 'desktop')
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const shell = process.platform === 'win32'

// Everything that gets bundled has to be there: a missing piece would make an installer that cannot start.
const need = Object.values(programPaths(id)).filter(Boolean).map(parts => path.join(buildDir, ...parts))
need.push(path.join(root, 'web', '.output', 'public', '200.html'), path.join(root, 'THIRD_PARTY_NOTICES.md'))
const missing = need.filter(file => !fs.existsSync(file))
if (missing.length > 0) throw new Error(`cannot package yet, these are missing:\n  ${missing.map(f => path.relative(root, f)).join('\n  ')}`)

const targets = {
  'darwin-arm64': ['--mac', 'dmg', '--arm64'],
  'win32-x64': ['--win', 'nsis', '--x64'],
  'linux-x64': ['--linux', 'AppImage', 'deb', '--x64'],
}[id]

group(`installer for ${id}`)
run(npm, ['ci'], { cwd: desktop, shell })
// Electron's own download step does not run under `npm ci` here, and its license files are bundled.
run('node', [path.join('node_modules', 'electron', 'install.js')], { cwd: desktop })
run(npm, ['run', 'build'], { cwd: desktop, shell })
fs.rmSync(path.join(desktop, 'release'), { recursive: true, force: true })
run(npx, ['electron-builder', ...targets, '--publish', 'never'], { cwd: desktop, shell })
endGroup()
