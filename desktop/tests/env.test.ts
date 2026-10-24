import { describe, expect, it } from 'vitest'
import { apiEnv, ollamaEnv, type Ports } from '../src/env'
import { dataDirs, layout } from '../src/layout'

const ports: Ports = { ollama: 11500, api: 8765 }
const dirs = dataDirs('/users/x/AppData/Slothshot')
const paths = layout('/apps/Slothshot/resources', 'darwin')

describe('ollamaEnv', () => {
  it('holds Ollama to one model and one request at a time', () => {
    const env = ollamaEnv(ports, dirs, {}, 'darwin')
    expect(env.OLLAMA_MAX_LOADED_MODELS).toBe('1')
    expect(env.OLLAMA_NUM_PARALLEL).toBe('1')
    expect(env.OLLAMA_KEEP_ALIVE).toBe('30s')
  })

  it('binds to loopback and disables cloud inference', () => {
    const env = ollamaEnv(ports, dirs, {}, 'darwin')
    expect(env.OLLAMA_HOST).toBe('127.0.0.1:11500')
    expect(env.OLLAMA_NO_CLOUD).toBe('1')
  })

  it('redirects the home folder on Windows as well as the HOME variable', () => {
    expect(ollamaEnv(ports, dirs, {}, 'win32').USERPROFILE).toBe(dirs.ollamaHome)
    expect(ollamaEnv(ports, dirs, {}, 'darwin').USERPROFILE).toBeUndefined()
  })

  it("does not let the user's own Ollama settings leak in", () => {
    const env = ollamaEnv(ports, dirs, { OLLAMA_HOST: '0.0.0.0:1', OLLAMA_KEEP_ALIVE: '24h' }, 'darwin')
    expect(env.OLLAMA_HOST).toBe('127.0.0.1:11500')
    expect(env.OLLAMA_KEEP_ALIVE).toBe('30s')
  })
})

describe('apiEnv', () => {
  it('points the api at loopback and the bundled Ollama', () => {
    const env = apiEnv(ports, dirs, paths, 4242, {}, 'darwin')
    expect(env.SLOTHSHOT_HOST).toBe('127.0.0.1')
    expect(env.SLOTHSHOT_PORT).toBe('8765')
    expect(env.SLOTHSHOT_OLLAMA_URL).toBe('http://127.0.0.1:11500')
    expect(env.SLOTHSHOT_PARENT_PID).toBe('4242')
  })

  it("does not let the user's own SLOTHSHOT_ settings leak in", () => {
    const env = apiEnv(ports, dirs, paths, 1, { SLOTHSHOT_PORT: '9999' }, 'darwin')
    expect(env.SLOTHSHOT_PORT).toBe('8765')
  })
})
