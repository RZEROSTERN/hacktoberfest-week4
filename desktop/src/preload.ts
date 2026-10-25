// Runs sandboxed, before the page. It exposes one read-only value: where the local api listens.
import { contextBridge } from 'electron'

const PREFIX = '--slothshot-api-base='

const arg = process.argv.find(a => a.startsWith(PREFIX))
const apiBase = arg ? arg.slice(PREFIX.length) : ''

if (/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(apiBase)) {
  contextBridge.exposeInMainWorld('desktop', { apiBase })
}
