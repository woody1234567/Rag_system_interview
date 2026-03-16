import { createFastApiClient } from '../../utils/fastapiClient'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const client = createFastApiClient({ baseUrl: config.public.fastapiBaseUrl })

  try {
    return await client.index()
  } catch (error: any) {
    throw createError({
      statusCode: error?.statusCode || 502,
      statusMessage: error?.statusMessage || 'FastAPI index failed',
      data: error?.data || { code: 'FASTAPI_INDEX_FAILED' },
    })
  }
})
