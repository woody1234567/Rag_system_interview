import { readBody } from 'h3'

import type { RagQueryRequest } from '../../../app/types/rag'
import { normalizeRagResult } from '../../../app/utils/ragNormalize'
import { createFastApiClient } from '../utils/fastapiClient'

export default defineEventHandler(async (event) => {
  const body = await readBody<RagQueryRequest>(event)
  if (!body?.question?.trim()) {
    throw createError({ statusCode: 400, statusMessage: 'question is required' })
  }

  const config = useRuntimeConfig(event)
  const client = createFastApiClient({ baseUrl: config.public.fastapiBaseUrl })

  try {
    const raw = await client.query(body)
    return normalizeRagResult(raw)
  } catch (error: any) {
    throw createError({
      statusCode: error?.statusCode || 502,
      statusMessage: error?.statusMessage || 'FastAPI query failed',
      data: error?.data || { code: 'FASTAPI_QUERY_FAILED' },
    })
  }
})
