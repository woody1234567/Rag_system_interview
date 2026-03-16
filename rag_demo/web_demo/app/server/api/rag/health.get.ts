import { createFastApiClient } from '../../utils/fastapiClient'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const client = createFastApiClient({ baseUrl: config.public.fastapiBaseUrl })

  try {
    return await client.health()
  } catch {
    return { status: 'down' }
  }
})
