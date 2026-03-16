import type {
  RagHealthResponse,
  RagIndexResponse,
  RagQueryRequest,
  RagQueryResponse,
} from '../../types/rag'

interface CreateFastApiClientOptions {
  baseUrl: string
  fetcher?: typeof $fetch
}

export function createFastApiClient(options: CreateFastApiClientOptions) {
  const fetcher = options.fetcher ?? $fetch
  const base = options.baseUrl.replace(/\/$/, '')

  return {
    query: (payload: RagQueryRequest) =>
      fetcher<RagQueryResponse>(`${base}/v1/rag/query`, {
        method: 'POST',
        body: payload,
        timeout: 30000,
      }),
    index: () =>
      fetcher<RagIndexResponse>(`${base}/v1/rag/index`, {
        method: 'POST',
        timeout: 120000,
      }),
    health: () =>
      fetcher<RagHealthResponse>(`${base}/healthz`, {
        method: 'GET',
        timeout: 10000,
      }),
  }
}
