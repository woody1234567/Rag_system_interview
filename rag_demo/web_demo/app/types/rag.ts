export interface RagQueryRequest {
  question: string
  question_type?: string
  include_debug?: boolean
}

export interface RagQueryResponse {
  answer: string
  refusal: boolean
  reason: string
  sources: number[]
  gate: Record<string, unknown> | null
  retrieval_debug: Record<string, unknown> | null
}

export interface RagIndexResponse {
  chunks: number
  status: string
}

export interface RagHealthResponse {
  status: string
}

export interface RagUploadResponse {
  filename: string
  status: string
}

export interface PingResponse {
  status: string
}

export interface ClearResponse {
  status: string
}
