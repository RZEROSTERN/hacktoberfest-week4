// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  // SPA only: the desktop shell loads the files produced by `nuxt generate`.
  ssr: false,
  modules: ['@nuxt/eslint'],
  css: ['~/assets/css/main.css'],
  devtools: { enabled: true },
  typescript: { strict: true },
  runtimeConfig: {
    public: {
      // Development default; override with NUXT_PUBLIC_API_BASE.
      // The packaged app gets the real URL from the desktop preload instead.
      apiBase: 'http://127.0.0.1:8765'
    }
  }
})
