// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  runtimeConfig: {
    public: {
      fastapiBaseUrl: process.env.NUXT_PUBLIC_FASTAPI_BASE_URL || 'http://127.0.0.1:8000',
    },
  },
})
