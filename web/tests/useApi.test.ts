import { describe, expect, it } from 'vitest'
import { resolveApiBase } from '~/composables/useApi'

describe('resolveApiBase', () => {
  it('prefers the desktop preload over runtimeConfig', () => {
    expect(resolveApiBase('http://127.0.0.1:9000', 'http://127.0.0.1:8765')).toBe(
      'http://127.0.0.1:9000'
    )
  })

  it('falls back to runtimeConfig in a plain browser', () => {
    expect(resolveApiBase(undefined, 'http://127.0.0.1:8765')).toBe('http://127.0.0.1:8765')
  })

  it('strips trailing slashes so paths do not double up', () => {
    expect(resolveApiBase(undefined, 'http://127.0.0.1:8765/')).toBe('http://127.0.0.1:8765')
    expect(resolveApiBase('http://127.0.0.1:9000///', 'x')).toBe('http://127.0.0.1:9000')
  })
})
