// Packs the api into one program (desktop/build/api/slothshot-api[.exe]) with PyInstaller, which cannot cross-build:
// it has to run on the system the program is for. Python 3.12 and the locked libraries come from uv.
import path from 'node:path'
import { buildDir, endGroup, group, platformId, rmrf, root, run } from './lib.mjs'

platformId()
const api = path.join(root, 'api')
group('api (PyInstaller)')
rmrf(path.join(buildDir, 'api'))
run('uv', ['sync', '--frozen', '--python', '3.12'], { cwd: api })
run(
  'uv',
  ['run', '--frozen', 'pyinstaller', '--noconfirm', '--clean', '--distpath', path.join(buildDir, 'api'), '--workpath', path.join(root, '.dev', 'pyinstaller'), 'slothshot-api.spec'],
  { cwd: api },
)
endGroup()
