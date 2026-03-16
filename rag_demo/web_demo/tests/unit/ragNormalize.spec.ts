import { describe, expect, it } from 'vitest'

import { normalizeRagResult } from '../../app/utils/ragNormalize'

describe('normalizeRagResult', () => {
  it('returns safe defaults when fields are missing', () => {
    const out = normalizeRagResult({ answer: 'x' })

    expect(out).toEqual({
      answer: 'x',
      refusal: false,
      reason: '',
      sources: [],
      gate: null,
      retrieval_debug: null,
    })
  })
})
