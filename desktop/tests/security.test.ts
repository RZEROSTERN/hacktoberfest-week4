import { describe, expect, it } from 'vitest'
import { isAllowedExternal, isAllowedRequest, isAppUrl } from '../src/security'

const API = 'http://127.0.0.1:8765'

describe('isAppUrl', () => {
  it('accepts the app origin and nothing else', () => {
    expect(isAppUrl('app://slothshot/index.html')).toBe(true)
    expect(isAppUrl('app://somewhere-else/index.html')).toBe(false)
    expect(isAppUrl('https://slothshot/index.html')).toBe(false)
    expect(isAppUrl('not a url')).toBe(false)
  })
})

describe('isAllowedExternal', () => {
  it('opens only the Ollama library, over https', () => {
    expect(isAllowedExternal('https://ollama.com/library')).toBe(true)
    expect(isAllowedExternal('http://ollama.com/library')).toBe(false)
    expect(isAllowedExternal('https://evil.example/ollama.com')).toBe(false)
  })
})

describe('isAllowedRequest', () => {
  it('allows the app itself and the local api', () => {
    expect(isAllowedRequest('app://slothshot/', API)).toBe(true)
    expect(isAllowedRequest(`${API}/api/status`, API)).toBe(true)
  })

  it('refuses the open internet', () => {
    expect(isAllowedRequest('https://example.com', API)).toBe(false)
    // A different port is a different origin, so another local server is not trusted either.
    expect(isAllowedRequest('http://127.0.0.1:9999/', API)).toBe(false)
  })
})
