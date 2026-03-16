import { createFastApiClient } from '../utils/fastapiClient'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const client = createFastApiClient({ baseUrl: config.public.fastapiBaseUrl })

  const formParts = await readMultipartFormData(event)
  if (!formParts || formParts.length === 0) {
    throw createError({ statusCode: 400, statusMessage: 'No file uploaded' })
  }

  const filePart = formParts.find(p => p.name === 'file')
  if (!filePart || !filePart.data) {
    throw createError({ statusCode: 400, statusMessage: 'Missing file field' })
  }

  try {
    return await client.upload(filePart.data, filePart.filename || 'unknown.pdf', filePart.type || 'application/pdf')
  } catch (error: any) {
    throw createError({
      statusCode: error?.statusCode || 502,
      statusMessage: error?.statusMessage || 'FastAPI upload failed',
      data: error?.data || { code: 'FASTAPI_UPLOAD_FAILED' },
    })
  }
})
