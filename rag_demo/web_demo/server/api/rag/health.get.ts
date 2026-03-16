import type { RagHealthResponse } from '../../../app/types/rag'
import { createFastApiClient } from '../utils/fastapiClient'

export default defineEventHandler(async (event): Promise<RagHealthResponse> => {
  const config = useRuntimeConfig(event)
  const client = createFastApiClient({ baseUrl: config.public.fastapiBaseUrl })

  try {
    return await client.health()
  } catch {
    return { status: 'down' }
  }
})
