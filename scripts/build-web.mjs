// Generates the web app as static files (web/.output/public). The result is the same on every system.
import path from 'node:path'
import { endGroup, group, root, run } from './lib.mjs'

const web = path.join(root, 'web')
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
group('web (Nuxt generate)')
run(npm, ['ci'], { cwd: web, shell: process.platform === 'win32' })
run(npm, ['run', 'generate'], { cwd: web, shell: process.platform === 'win32' })
endGroup()
