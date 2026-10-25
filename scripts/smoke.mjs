// Starts the programs an installer carries and checks they work, from the folder they were packaged into:
//   node scripts/smoke.mjs --resources <the packaged app's resources folder>
//   node scripts/smoke.mjs                         (checks desktop/build, what is about to be packaged)
//
// What it proves, on each operating system:
//   1. every bundled program is there and starts (Ollama --version);
//   2. the bundled Ollama serves on loopback and answers its own API;
//   3. the packaged api binary starts and answers /health;
//   4. the api can reach that Ollama across a process boundary (/api/engine says reachable);
//   5. the generated web app is in the bundle.
//
// It deliberately does NOT download a model or run inference. The smallest vision model is about
// 1.9 GB, and pulling it onto three CI runners would be slow and would amount to running the
// product's own workload on someone else's machine. Inference is proven locally instead; see
// docs/BENCHMARKS.md. The job fails if any of the above fails.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { buildDir, capture, endGroup, group, platformId, programPaths, root } from './lib.mjs'

const argv = process.argv.slice(2)
const resourcesArg = argv.includes('--resources') ? argv[argv.indexOf('--resources') + 1] : null
const base = resourcesArg ? path.resolve(root, resourcesArg) : buildDir
const id = platformId()
const paths = programPaths(id)
const children = []
let failures = 0

function fail(message) {
  console.error(`  FAIL  ${message}`)
  failures++
}
function pass(message) {
  console.log(`  ok    ${message}`)
}

function killTree(child) {
  if (!child || child.exitCode !== null) return
  try {
    if (process.platform === 'win32') capture('taskkill', ['/PID', String(child.pid), '/T', '/F'])
    else process.kill(-child.pid, 'SIGKILL')
  } catch {
    // already gone
  }
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })
}

async function until(check, timeoutMs, stepMs = 500) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      if (await check()) return true
    } catch {
      // not up yet
    }
    await new Promise(resolve => setTimeout(resolve, stepMs))
  }
  return false
}

group(`smoke test (${resourcesArg ? 'packaged' : 'built'}, ${id})`)
console.log(`checking ${base}`)

// 1. Every bundled program is present and runs.
const ollamaBinary = path.join(base, ...paths.ollama)
const apiBinary = path.join(base, ...paths.api)
for (const [name, file] of [['ollama', ollamaBinary], ['api', apiBinary]]) {
  if (fs.existsSync(file)) pass(`${name} is bundled`)
  else fail(`${name} is missing at ${path.relative(base, file)}`)
}

// 5. The web app the shell loads. Before packaging it is still where Nuxt generated it;
// electron-builder is what copies it to resources/web.
const webRoot = resourcesArg
  ? path.join(base, 'web')
  : path.join(root, 'web', '.output', 'public')
const webEntry = path.join(webRoot, 'index.html')
if (fs.existsSync(webEntry)) pass('the web app is bundled')
else fail(`the web app is missing at ${path.relative(root, webEntry)}`)

if (failures === 0) {
  const version = capture(ollamaBinary, ['--version'])
  if (version.status === 0) pass(`ollama --version: ${version.stdout.trim().split('\n').pop()}`)
  else fail(`ollama --version failed: ${version.stderr.trim()}`)
}

// A folder whose name carries an accent, as a Windows user name may, which exercises the paths.
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'slothshot-humo-'))

try {
  if (failures === 0) {
    const ollamaPort = await freePort()
    const apiPort = await freePort()
    const ollamaHome = path.join(work, 'ollama-home')
    fs.mkdirSync(ollamaHome, { recursive: true })

    // 2. The bundled Ollama, on loopback, with its own home so a system-wide one is untouched.
    const ollama = spawn(ollamaBinary, ['serve'], {
      env: {
        ...process.env,
        HOME: ollamaHome,
        USERPROFILE: ollamaHome,
        OLLAMA_HOST: `127.0.0.1:${ollamaPort}`,
        OLLAMA_MODELS: path.join(work, 'ollama-models'),
        OLLAMA_NO_CLOUD: '1',
        OLLAMA_MAX_LOADED_MODELS: '1',
        OLLAMA_NUM_PARALLEL: '1',
      },
      detached: process.platform !== 'win32',
      stdio: 'ignore',
    })
    children.push(ollama)

    const ollamaUp = await until(async () => {
      const response = await fetch(`http://127.0.0.1:${ollamaPort}/api/tags`)
      return response.ok
    }, 60_000)
    if (ollamaUp) pass('the bundled Ollama serves on loopback')
    else fail('the bundled Ollama did not answer /api/tags')

    // 3. The packaged api, started the way the desktop shell starts it.
    const api = spawn(apiBinary, [], {
      env: {
        ...process.env,
        SLOTHSHOT_HOST: '127.0.0.1',
        SLOTHSHOT_PORT: String(apiPort),
        SLOTHSHOT_DATA_DIR: path.join(work, 'data'),
        SLOTHSHOT_MODELS_DIR: path.join(work, 'models'),
        SLOTHSHOT_OLLAMA_URL: `http://127.0.0.1:${ollamaPort}`,
      },
      detached: process.platform !== 'win32',
      stdio: 'ignore',
    })
    children.push(api)

    const apiUp = await until(async () => {
      const response = await fetch(`http://127.0.0.1:${apiPort}/health`)
      return response.ok && (await response.json()).status === 'ok'
    }, 120_000)
    if (apiUp) pass('the packaged api answers /health')
    else fail('the packaged api did not answer /health')

    // 4. The two of them, talking to each other.
    if (apiUp && ollamaUp) {
      const response = await fetch(`http://127.0.0.1:${apiPort}/api/engine`)
      const body = response.ok ? await response.json() : null
      if (body?.reachable === true) pass('the api reached the bundled Ollama')
      else fail(`the api could not reach the bundled Ollama (${JSON.stringify(body)})`)

      if (Array.isArray(body?.recommended) && body.recommended.length > 0) {
        pass(`the model catalog is readable (${body.recommended.length} recommended)`)
      } else {
        fail('the model catalog was not bundled with the api')
      }
    }
  }
} finally {
  for (const child of children) killTree(child)
  fs.rmSync(work, { recursive: true, force: true })
}

endGroup()
if (failures > 0) {
  console.error(`\n${failures} smoke check(s) failed`)
  process.exit(1)
}
console.log('\nall smoke checks passed')
