// The build, in order, defined once. `npm run dist` runs exactly these; .github/workflows/build.yml runs the
// same scripts in the same order, and scripts/dist.test.mjs fails if the two ever differ.
import { packagedResources } from './lib.mjs'

export const STEPS = [
  { id: 'fetch-ollama', script: 'fetch-ollama.mjs', title: 'Ollama (official release, CPU and Vulkan on Windows and Linux)' },
  { id: 'build-web', script: 'build-web.mjs', title: 'Web app' },
  { id: 'build-api', script: 'build-api.mjs', title: 'Api (PyInstaller)' },
  { id: 'smoke-built', script: 'smoke.mjs', title: 'Smoke test the built programs', args: () => [] },
  { id: 'package', script: 'package.mjs', title: 'Installer' },
  { id: 'smoke-packaged', script: 'smoke.mjs', title: 'Smoke test the packaged programs', args: () => ['--resources', packagedResources()] },
  { id: 'installer-sizes', script: 'installer-sizes.mjs', title: 'Installer sizes' },
]

/** Which steps to run for the command line options: --from <id>, --only <id>, --skip-smoke. */
export function selectSteps({ from, only, skipSmoke }, steps = STEPS) {
  const ids = steps.map(step => step.id)
  for (const [flag, id] of [['--from', from], ['--only', only]]) {
    if (id !== undefined && !ids.includes(id)) throw new Error(`${flag} ${id}: no such step. The steps are: ${ids.join(', ')}`)
  }
  if (from !== undefined && only !== undefined) throw new Error('use --from or --only, not both')
  let selected = steps
  if (only !== undefined) selected = steps.filter(step => step.id === only)
  else if (from !== undefined) selected = steps.slice(ids.indexOf(from))
  if (skipSmoke) selected = selected.filter(step => !step.id.startsWith('smoke'))
  return selected
}
