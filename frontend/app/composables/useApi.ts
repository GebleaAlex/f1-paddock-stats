// Typed data loading from the Paddock Stats API. The URL is also the cache key, so pages that ask for the same
// data share one request, a changed URL (another season, another filter) refetches, and the first visit is
// rendered on the server.
export function useApi<T>(path: string | (() => string), opts: { lazy?: boolean; server?: boolean } = {}) {
  const url = () => `/api${typeof path === 'function' ? path() : path}`
  return useAsyncData<T>(url, () => $fetch<T>(url()), opts)
}

/**
 * Stops a detail page from rendering empty when its data did not load. A 404, or a 422 for an id the API cannot
 * parse (/seasons/abc), becomes the "not found" page; any other failure (API down, 500) becomes the error page.
 */
export function notFoundIf(error: Ref<unknown>, what = 'Page') {
  const e = error.value as { statusCode?: number } | null
  if (!e) return
  if (e.statusCode === 404 || e.statusCode === 422) {
    throw createError({ statusCode: 404, statusMessage: `${what} not found`, fatal: true })
  }
  throw createError({ statusCode: e.statusCode ?? 500, statusMessage: 'The data could not be loaded', fatal: true })
}
