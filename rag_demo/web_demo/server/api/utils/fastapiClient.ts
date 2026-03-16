import type {
  RagHealthResponse,
  RagIndexResponse,
  RagQueryRequest,
  RagQueryResponse,
  RagUploadResponse,
} from '../../../app/types/rag'

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
    upload: (fileData: Uint8Array | Buffer, filename: string, contentType: string) => {
      const formData = new FormData()
      formData.append('file', new Blob([fileData], { type: contentType }), filename)
      return fetcher<RagUploadResponse>(`${base}/v1/rag/upload`, {
        method: 'POST',
        body: formData,
        timeout: 120000,
      })
    },
  }
}

