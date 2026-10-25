// Builds the installer for the system this runs on, with the same steps as CI (.github/workflows/build.yml).
//   npm run dist                              everything, in order
//   npm run dist -- --from build-api          resume at a step (after fixing what stopped it)
//   npm run dist -- --only package            one step
//   npm run dist -- --skip-smoke --no-preflight --dry-run --list
// This is the fallback for a release day when CI is not available: the installer ends up in desktop/release/.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { formatBytes, platformId, root } from './lib.mjs'
import { STEPS, selectSteps } from './steps.mjs'

const argv = process.argv.slice(2)
const flag = name => argv.includes(name)
const value = name => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : undefined)

if (flag('--help') || flag('-h')) {
  console.log(`npm run dist [-- options]\n\n  --list          show the steps\n  --dry-run       show what would run\n  --from <step>   start at a step\n  --only <step>   run one step\n  --skip-smoke    skip the smoke tests\n`)
  process.exit(0)
}

const id = platformId()
if (flag('--list')) {
  STEPS.forEach((step, i) => console.log(`${i + 1}. ${step.id}  ${step.title}`))
  process.exit(0)
}

let steps
try {
  steps = selectSteps({ from: value('--from'), only: value('--only'), skipSmoke: flag('--skip-smoke') })
} catch (error) {
  console.error(error.message)
  process.exit(2)
}

console.log(`Slothshot installer for ${id}`)

console.log(`\nSteps: ${steps.map(step => step.id).join(' > ')}`)
if (flag('--dry-run')) process.exit(0)

const started = Date.now()
for (const [index, step] of steps.entries()) {
  console.log(`\n[${index + 1}/${steps.length}] ${step.title}`)
  const at = Date.now()
  const result = spawnSync(process.execPath, [path.join(root, 'scripts', step.script), ...(step.args?.() ?? [])], { cwd: root, stdio: 'inherit' })
  if (result.status !== 0) {
    console.error(`\nStopped at "${step.id}" (${result.status ?? result.signal}). Fix it, then continue with:\n  npm run dist -- --from ${step.id}`)
    process.exit(1)
  }
  console.log(`  ${step.id} done in ${Math.round((Date.now() - at) / 1000)} s`)
}
const minutes = ((Date.now() - started) / 60000).toFixed(1)
console.log(`\nDone in ${minutes} min. The installer is in desktop/release/ (installers up to ${formatBytes(1.5e9)} are accepted).`)
