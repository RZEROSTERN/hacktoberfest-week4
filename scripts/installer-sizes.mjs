// Lists the installers in desktop/release with their size and SHA-256, writes them to the job summary when run by
// GitHub Actions, writes a .sha256 file beside each, and fails if one is over the limit in versions.json.
import fs from 'node:fs'
import path from 'node:path'
import { formatBytes, root, sha256File, versions } from './lib.mjs'

const release = path.join(root, 'desktop', 'release')
const installer = /\.(dmg|exe|AppImage|deb)$/
const files = fs.existsSync(release) ? fs.readdirSync(release).filter(name => installer.test(name) && fs.statSync(path.join(release, name)).isFile()) : []
if (files.length === 0) {
  console.error('no installer was found in desktop/release')
  process.exit(1)
}

const limit = versions.maxInstallerBytes
const rows = files.sort().map((name) => {
  const file = path.join(release, name)
  const bytes = fs.statSync(file).size
  const sha = sha256File(file)
  fs.writeFileSync(`${file}.sha256`, `${sha}  ${name}\n`)
  return { name, bytes, sha, over: bytes > limit }
})

const lines = [
  `### Installers (limit ${formatBytes(limit)})`,
  '',
  '| File | Size | SHA-256 |',
  '| --- | ---: | --- |',
  ...rows.map(r => `| ${r.name} | ${formatBytes(r.bytes)}${r.over ? ' **over the limit**' : ''} | \`${r.sha}\` |`),
  '',
]
console.log(lines.join('\n'))
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${lines.join('\n')}\n`)
if (rows.some(r => r.over)) {
  console.error(`an installer is over ${formatBytes(limit)}: stop and choose how to make it smaller`)
  process.exit(1)
}
