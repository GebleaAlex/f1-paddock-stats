// Forwards /api/* to the FastAPI service, for both server-side rendering and the browser.
export default defineEventHandler((event) => {
  const { apiBase } = useRuntimeConfig(event)
  const path = event.path.replace(/^\/api/, '')
  return proxyRequest(event, `${apiBase}/api${path}`)
})
