export default defineEventHandler(async () => {
  return await $fetch('/v1/rag/clear', {
    baseURL: process.env.FASTAPI_URL || 'http://localhost:8000',
    method: 'POST',
  }).catch((error) => {
    throw createError({
      statusCode: error?.response?.status || 500,
      statusMessage: error?.message || 'Clear failed',
      data: error?.data,
    })
  })
})
