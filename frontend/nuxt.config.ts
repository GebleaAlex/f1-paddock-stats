// Paddock Stats frontend. Pages are server-rendered so every shared link has a real title and description;
// the browser and the Nuxt server both call the API through /api (see server/api/[...path].ts).
export default defineNuxtConfig({
  compatibilityDate: '2026-10-01',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    // Where the FastAPI service listens. Override with NUXT_API_BASE.
    apiBase: 'http://127.0.0.1:8020',
    public: {
      siteName: 'Paddock Stats',
      // Public address of the site, used for absolute links in social previews. Override with NUXT_PUBLIC_SITE_URL.
      siteUrl: 'http://localhost:3000',
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'en' },
      titleTemplate: '%s · Paddock Stats',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
        { name: 'theme-color', content: '#f9f9f7', media: '(prefers-color-scheme: light)' },
        { name: 'theme-color', content: '#0d0d0d', media: '(prefers-color-scheme: dark)' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },
  typescript: { strict: true },
})
