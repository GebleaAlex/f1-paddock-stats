// A value kept in the URL query string, so tabs, filters and selections are part of the link people share.
// Defaults are left out of the URL to keep links short.
export function useQueryState(key: string, fallback: string) {
  const route = useRoute()
  const router = useRouter()
  return computed<string>({
    get: () => {
      const v = route.query[key]
      return typeof v === 'string' && v !== '' ? v : fallback
    },
    set: (value) => {
      const query = { ...route.query }
      if (value === fallback || value === '') delete query[key]
      else query[key] = value
      router.replace({ query })
    },
  })
}

export function useQueryNumber(key: string, fallback: number) {
  const s = useQueryState(key, String(fallback))
  return computed<number>({
    get: () => (Number.isFinite(Number(s.value)) ? Number(s.value) : fallback),
    set: (v) => (s.value = String(v)),
  })
}
