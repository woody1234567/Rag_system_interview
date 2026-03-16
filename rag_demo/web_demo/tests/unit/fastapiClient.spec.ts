import { describe, expect, it, vi } from 'vitest'

import { createFastApiClient } from '../../app/server/utils/fastapiClient'

describe('fastapi client', () => {
  it('forwards query payload to FastAPI and returns response', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      answer: 'demo answer',
      refusal: false,
      reason: 'ok',
      sources: [1],
      gate: { decision: 'allow_answer' },
      retrieval_debug: null,
    })

    const client = createFastApiClient({ baseUrl: 'http://127.0.0.1:8000', fetcher })

    const result = await client.query({ question: 'What is RAG?', include_debug: false })

    expect(fetcher).toHaveBeenCalledWith('http://127.0.0.1:8000/v1/rag/query', {
      method: 'POST',
      body: { question: 'What is RAG?', include_debug: false },
      timeout: 30000,
    })
    expect(result.answer).toBe('demo answer')
  })

  it('calls index endpoint and returns chunks', async () => {
    const fetcher = vi.fn().mockResolvedValue({ chunks: 256, status: 'completed' })
    const client = createFastApiClient({ baseUrl: 'http://127.0.0.1:8000', fetcher })

    const result = await client.index()

    expect(fetcher).toHaveBeenCalledWith('http://127.0.0.1:8000/v1/rag/index', {
      method: 'POST',
      timeout: 120000,
    })
    expect(result.chunks).toBe(256)
  })

  it('calls health endpoint', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'ok' })
    const client = createFastApiClient({ baseUrl: 'http://127.0.0.1:8000', fetcher })

    const result = await client.health()

    expect(fetcher).toHaveBeenCalledWith('http://127.0.0.1:8000/healthz', {
      method: 'GET',
      timeout: 10000,
    })
    expect(result.status).toBe('ok')
  })
})
