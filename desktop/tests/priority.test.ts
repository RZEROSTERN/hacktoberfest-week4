import os from 'node:os'
import { describe, expect, it, vi } from 'vitest'
import { BACKGROUND_PRIORITY, lowerPriority } from '../src/priority'

describe('lowerPriority', () => {
  it('asks for below-normal, not the idle class', () => {
    expect(BACKGROUND_PRIORITY).toBe(os.constants.priority.PRIORITY_BELOW_NORMAL)
    const setPriority = vi.fn()
    expect(lowerPriority(123, setPriority)).toBe(true)
    expect(setPriority).toHaveBeenCalledWith(123, BACKGROUND_PRIORITY)
  })

  it('reports failure instead of throwing when the platform refuses', () => {
    const setPriority = vi.fn(() => {
      throw new Error('EPERM')
    })
    expect(lowerPriority(123, setPriority)).toBe(false)
  })
})
