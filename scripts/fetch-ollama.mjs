// Downloads the official standalone Ollama for this system into desktop/build/ollama/, checks it against the
// SHA-256 pinned in versions.json, and keeps what the app uses:
//   macOS    ollama, its llama-server, the Metal libraries and every license (as before).
//   Windows  ollama.exe and lib/ollama with the CPU and Vulkan backends. The CUDA folders (cuda_v12, cuda_v13)
//            are about 1.3 GiB of the 1.85 GiB and would put the installer past the 1.5 GB limit; Vulkan is
//            enabled by default in Ollama when its backend is present, and runs on AMD, Intel and NVIDIA
//            drivers. See docs/DECISIONS.md.
//   Linux    the same, from the .tar.zst: bin/ollama and lib/ollama keep the layout Ollama expects.
// The binaries are Ollama's own and stay untouched; only whole folders are left out.
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { buildDir, download, downloadsDir, endGroup, formatBytes, group, mkdirp, platformId, programPaths, rmrf, run, sizeOf, tarProgram, versions } from './lib.mjs'

const id = platformId()
const { version, assets, licenseSha256 } = versions.ollama
const asset = assets[id]
const out = path.join(buildDir, 'ollama')

group(`Ollama ${version} for ${id}`)
const archive = await download(
  `https://github.com/ollama/ollama/releases/download/${version}/${asset.file}`,
  path.join(downloadsDir, `ollama-${version}-${asset.file}`),
  asset.sha256,
)
// The archives carry the licenses of Ollama's parts but not Ollama's own, so that comes from the same tag.
const license = await download(
  `https://raw.githubusercontent.com/ollama/ollama/${version}/LICENSE`,
  path.join(downloadsDir, `ollama-LICENSE-${version}`),
  licenseSha256,
)

rmrf(out)
mkdirp(out)

if (id === 'darwin-arm64') {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'slothshot-ollama-'))
  try {
    run(tarProgram(), ['-xzf', archive, '-C', work])
    for (const name of ['ollama', 'llama-server']) fs.copyFileSync(path.join(work, name), path.join(out, name))
    for (const dir of ['mlx_metal_v3', 'mlx_metal_v4']) fs.cpSync(path.join(work, dir), path.join(out, dir), { recursive: true })
    for (const name of fs.readdirSync(work)) {
      if (/LICENSE|NOTICE/.test(name)) fs.copyFileSync(path.join(work, name), path.join(out, name))
    }
  } finally {
    rmrf(work)
  }
} else {
  // GNU tar (Linux) and bsdtar (Windows 10 and later) both take --exclude with a pattern; `*` crosses folders.
  const leave = ['--exclude', 'lib/ollama/cuda_*', '--exclude', 'lib/ollama/rocm*']
  const flags = asset.file.endsWith('.tar.zst') ? ['--zstd', '-xf'] : ['-xf']
  run(tarProgram(), [...flags, archive, '-C', out, ...leave])
}
fs.copyFileSync(license, path.join(out, 'LICENSE'))
fs.writeFileSync(path.join(out, 'VERSION'), `${version}\n`)

// What was asked for must be what is there.
const binary = path.join(buildDir, ...programPaths(id).ollama)
if (!fs.existsSync(binary)) throw new Error(`the archive did not contain ${path.relative(buildDir, binary)}`)
if (id !== 'darwin-arm64') {
  const lib = path.join(out, 'lib', 'ollama')
  const left = fs.readdirSync(lib).filter(name => /^(cuda|rocm)/.test(name))
  if (left.length > 0) throw new Error(`GPU libraries were not removed: ${left.join(', ')}`)
  if (!fs.existsSync(path.join(lib, 'vulkan'))) throw new Error('the Vulkan backend is missing from the archive')
}
if (process.platform !== 'win32') fs.chmodSync(binary, 0o755)
console.log(`Ollama ${version} ready in ${path.relative(process.cwd(), out)} (${formatBytes(sizeOf(out))})`)
endGroup()
