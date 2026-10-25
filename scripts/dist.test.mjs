// `npm run dist` and .github/workflows/build.yml must run the same scripts in the same order.
// Run with: node --test scripts/
//
// Why this exists: the two are easy to change independently, and the failure mode is a release
// built by steps nobody ran locally, or a local build that passes while CI cannot.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { STEPS, selectSteps } from './steps.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workflow = fs.readFileSync(path.join(root, '.github', 'workflows', 'build.yml'), 'utf8')

/** The scripts build.yml runs, in order, as they appear in its `run:` lines. */
function scriptsInWorkflow() {
  return [...workflow.matchAll(/node scripts\/([\w.-]+\.mjs)/g)].map(match => match[1])
}

test('build.yml runs exactly the steps npm run dist runs, in order', () => {
  assert.deepEqual(scriptsInWorkflow(), STEPS.map(step => step.script))
})

test('every step points at a script that exists', () => {
  for (const step of STEPS) {
    assert.ok(
      fs.existsSync(path.join(root, 'scripts', step.script)),
      `${step.id} points at scripts/${step.script}, which is not there`,
    )
  }
})

test('the packaged smoke test is given the resources folder, the built one is not', () => {
  const built = STEPS.find(step => step.id === 'smoke-built')
  const packaged = STEPS.find(step => step.id === 'smoke-packaged')
  assert.deepEqual(built.args(), [])
  assert.equal(packaged.args()[0], '--resources')
  // The same path CI passes for this platform.
  assert.ok(workflow.includes('--resources "${{ matrix.resources }}"'))
})

test('the installer is smoke-tested after it is built, not only before', () => {
  const ids = STEPS.map(step => step.id)
  assert.ok(ids.indexOf('smoke-packaged') > ids.indexOf('package'))
  assert.ok(ids.indexOf('smoke-built') < ids.indexOf('package'))
})

test('selectSteps resumes, narrows and refuses a name it does not know', () => {
  assert.deepEqual(
    selectSteps({ from: 'package' }).map(s => s.id),
    ['package', 'smoke-packaged', 'installer-sizes'],
  )
  assert.deepEqual(selectSteps({ only: 'build-api' }).map(s => s.id), ['build-api'])
  assert.ok(!selectSteps({ skipSmoke: true }).some(s => s.id.startsWith('smoke')))
  assert.throws(() => selectSteps({ from: 'nope' }), /no such step/)
  assert.throws(() => selectSteps({ from: 'package', only: 'package' }), /not both/)
})

test('no workflow targets a branch named main', () => {
  // Branch references only, not prose: a comment explaining this rule contains the word too.
  const asBranch = [
    /branches:\s*\[[^\]]*\bmain\b/, // branches: [main, ...]
    /-\s*main\s*$/m, //                    branches:\n  - main
    /origin\/main\b/,
    /refs\/heads\/main\b/,
    /(base_ref|head_ref|ref_name|default_branch)\s*==\s*'main'/,
  ]
  for (const name of fs.readdirSync(path.join(root, '.github', 'workflows'))) {
    const text = fs.readFileSync(path.join(root, '.github', 'workflows', name), 'utf8')
    for (const pattern of asBranch) {
      assert.ok(!pattern.test(text), `${name} targets a branch named "main" (${pattern})`)
    }
  }
})

test('the branches workflows do target are master, develop and release/*', () => {
  const targeted = [...workflow.matchAll(/branches:\s*\[([^\]]*)\]/g)]
    .flatMap(match => match[1].split(',').map(name => name.trim()))
  assert.ok(targeted.length > 0)
  for (const branch of targeted) assert.ok(['master', 'develop'].includes(branch), branch)
})

test('every third-party action is pinned to a full commit SHA', () => {
  for (const name of fs.readdirSync(path.join(root, '.github', 'workflows'))) {
    const text = fs.readFileSync(path.join(root, '.github', 'workflows', name), 'utf8')
    for (const [, uses] of text.matchAll(/uses:\s*(\S+)/g)) {
      if (uses.startsWith('./')) continue // a workflow in this repository
      assert.match(uses, /@[0-9a-f]{40}$/, `${name}: ${uses} is not pinned to a commit SHA`)
    }
  }
})
