import type { RagQueryResponse } from '../types/rag'

export function normalizeRagResult(input: Partial<RagQueryResponse>): RagQueryResponse {
  return {
    answer: input.answer ?? '',
    refusal: input.refusal ?? false,
    reason: input.reason ?? '',
    sources: input.sources ?? [],
    gate: input.gate ?? null,
    retrieval_debug: input.retrieval_debug ?? null,
  }
}
