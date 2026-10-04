// Typed data loading from the Paddock Stats API. The URL is also the cache key, so pages that ask for the same
// data share one request, a changed URL (another season, another filter) refetches, and the first visit is
// rendered on the server.
export function useApi<T>(path: string | (() => string), opts: { lazy?: boolean; server?: boolean } = {}) {
  const url = () => `/api${typeof path === 'function' ? path() : path}`
  return useAsyncData<T>(url, () => $fetch<T>(url()), opts)
}

/** Throws a proper 404 page when the API says the item does not exist. */
export function notFoundIf(error: Ref<unknown>, what = 'Page') {
  const e = error.value as { statusCode?: number } | null
  if (e && e.statusCode === 404) {
    throw createError({ statusCode: 404, statusMessage: `${what} not found`, fatal: true })
  }
}
