import type { RagIndexResponse, RagQueryRequest, RagQueryResponse, RagUploadResponse } from '../types/rag'

export function useRagApi() {
  const queryRag = (payload: RagQueryRequest) =>
    $fetch<RagQueryResponse>('/api/rag/query', {
      method: 'POST',
      body: payload,
    })

  const buildIndex = () =>
    $fetch<RagIndexResponse>('/api/rag/build-index', {
      method: 'POST',
    })

  const checkHealth = () => $fetch<{ status: string }>('/api/rag/health')

  const uploadFile = (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return $fetch<RagUploadResponse>('/api/rag/upload', {
      method: 'POST',
      body: formData,
    })
  }

  return {
    queryRag,
    buildIndex,
    checkHealth,
    uploadFile,
  }
}

