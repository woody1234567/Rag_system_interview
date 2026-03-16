import type { RagIndexResponse, RagQueryRequest, RagQueryResponse } from '../types/rag'

export function useRagApi() {
  const queryRag = (payload: RagQueryRequest) =>
    $fetch<RagQueryResponse>('/api/rag/query', {
      method: 'POST',
      body: payload,
    })

  const buildIndex = () =>
    $fetch<RagIndexResponse>('/api/rag/index', {
      method: 'POST',
    })

  const checkHealth = () => $fetch<{ status: string }>('/api/rag/health')

  return {
    queryRag,
    buildIndex,
    checkHealth,
  }
}
