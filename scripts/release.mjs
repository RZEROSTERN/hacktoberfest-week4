// The checks and files a release needs, as plain functions (tested) with a small command line for the workflow:
//   node scripts/release.mjs verify <tag>               checks the tag against the versions in the repository
//   node scripts/release.mjs prepare <folder> <version> writes SHA256SUMS and RELEASE_NOTES.md in the folder
// A release is only ever created as a DRAFT by .github/workflows/release.yml; these files are what goes into it.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { formatBytes, root, sha256File } from './lib.mjs'

/** The four installers a complete release has, and how each is described. */
export const INSTALLERS = [
  { match: /\.dmg$/, system: 'macOS (Apple Silicon, macOS 14 or later)' },
  { match: /-setup\.exe$/, system: 'Windows 11 (x64)' },
  { match: /\.AppImage$/, system: 'Linux, any distribution with FUSE 2 (x64)' },
  { match: /\.deb$/, system: 'Linux Mint, Ubuntu and Debian (x64)' },
]

const TAG = /^v(\d+\.\d+\.\d+)(-[0-9A-Za-z.-]+)?$/

/** Problems with a release tag, given the versions the installers will carry. Empty means fine. */
export function checkTag(tag, desktopVersion, apiVersion) {
  const m = TAG.exec(tag)
  if (!m) return [`"${tag}" is not a version tag like v1.2.3 or v1.2.3-rc.1`]
  const problems = []
  const wanted = `${m[1]}${m[2] ?? ''}`
  if (desktopVersion !== wanted) problems.push(`the tag says ${wanted} but desktop/package.json says ${desktopVersion}, so the installers would be named after the wrong version`)
  if (apiVersion !== wanted) problems.push(`the tag says ${wanted} but api/pyproject.toml says ${apiVersion}`)
  return problems
}

export function readVersions() {
  const desktop = JSON.parse(fs.readFileSync(path.join(root, 'desktop', 'package.json'), 'utf8')).version
  const pyproject = fs.readFileSync(path.join(root, 'api', 'pyproject.toml'), 'utf8')
  const api = /^version\s*=\s*"([^"]+)"/m.exec(pyproject)?.[1]
  return { desktop, api }
}

/** The installer files in a folder (not the per-file .sha256 checksums), or an error if one of the four is missing. */
export function findInstallers(files) {
  const names = files.filter(name => !name.endsWith('.sha256'))
  const found = INSTALLERS.map(kind => ({ ...kind, file: names.find(name => kind.match.test(name)) }))
  const missing = found.filter(kind => !kind.file).map(kind => kind.system)
  if (missing.length > 0) throw new Error(`an installer is missing for: ${missing.join('; ')}`)
  return found
}

/** `sha256sum`-style lines, sorted by name, readable by `sha256sum -c` and `shasum -a 256 -c`. */
export function checksumLines(entries) {
  return entries
    .map(({ file, sha }) => ({ file, sha }))
    .sort((a, b) => a.file.localeCompare(b.file))
    .map(({ file, sha }) => `${sha}  ${file}`)
    .join('\n') + '\n'
}

export function renderNotes({ version, rows }) {
  const table = rows.map(r => `| ${r.system} | \`${r.file}\` | ${formatBytes(r.bytes)} |`).join('\n')
  return `# Slothshot ${version}

Turns a recorded client call into a draft proposal, entirely on your computer. These installers are **not signed**, so each system warns the first time you open the app; the steps are below.

| System | File | Size |
| --- | --- | ---: |
${table}

## Install

- **macOS.** Open the \`.dmg\` and drag Slothshot into Applications. The first time, macOS blocks it: open System Settings, then Privacy & Security, scroll down and click **Open Anyway** next to Slothshot.
- **Windows 11.** Run the \`-setup.exe\`. SmartScreen shows "Windows protected your PC": click **More info**, then **Run anyway**. It installs for your user and does not need administrator rights.
- **Linux, \`.deb\`** (Linux Mint, Ubuntu, Debian): \`sudo apt install ./slothshot_${version}_amd64.deb\`, then open Slothshot from the menu.
- **Linux, AppImage:** \`chmod +x Slothshot-${version}-x86_64.AppImage\` and run it. It needs FUSE 2 (\`sudo apt install libfuse2\`, or \`libfuse2t64\` on Ubuntu 24.04 and Mint 22). If it stops with a sandbox error, use the \`.deb\`.

## First launch

Slothshot asks to download its AI models once (about 7.2 GB, use Wi-Fi). After that it works offline. On Windows and Linux the language model runs on the CPU, or on a graphics card through Vulkan when its driver supports it; NVIDIA CUDA is not included. The Windows and Linux builds need a CPU with AVX2 (Intel since 2013, AMD since 2015).

## Check your download

\`SHA256SUMS\` lists the SHA-256 of every file here. macOS: \`shasum -a 256 -c SHA256SUMS --ignore-missing\`. Linux: \`sha256sum -c SHA256SUMS --ignore-missing\`. Windows (PowerShell): \`Get-FileHash .\\<file> -Algorithm SHA256\` and compare with the line in the list.

More in the [README](https://github.com/RZEROSTERN/hacktoberfest-week3#readme) and [docs/RELEASE_CHECKLIST.md](https://github.com/RZEROSTERN/hacktoberfest-week3/blob/master/docs/RELEASE_CHECKLIST.md).
`
}

/** Writes SHA256SUMS and RELEASE_NOTES.md into `dir` and returns the files to attach. */
export function prepare(dir, version) {
  const kinds = findInstallers(fs.readdirSync(dir))
  const rows = kinds.map(kind => {
    const file = path.join(dir, kind.file)
    return { ...kind, bytes: fs.statSync(file).size, sha: sha256File(file) }
  })
  fs.writeFileSync(path.join(dir, 'SHA256SUMS'), checksumLines(rows))
  fs.writeFileSync(path.join(dir, 'RELEASE_NOTES.md'), renderNotes({ version, rows }))
  return [...rows.map(r => r.file), 'SHA256SUMS']
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command, ...args] = process.argv.slice(2)
  if (command === 'verify') {
    const tag = args[0]
    const { desktop, api } = readVersions()
    const problems = checkTag(tag, desktop, api)
    if (problems.length > 0) {
      for (const p of problems) console.error(`::error::${p}`)
      process.exit(1)
    }
    console.log(`${tag} matches desktop ${desktop} and api ${api}`)
  } else if (command === 'prepare') {
    const files = prepare(path.resolve(args[0]), args[1])
    console.log(`prepared: ${files.join(', ')}`)
  } else if (command) {
    console.error(`unknown command "${command}"`)
    process.exit(2)
  }
}
