// Client-side sorting kept in the URL (?sort=wins or ?sort=-wins), for the big list pages.
export function useSorted<T extends object>(rows: Ref<T[] | null | undefined>, fallback: string) {
  const sort = useQueryState('sort', fallback)
  const key = computed(() => sort.value.replace(/^-/, ''))
  const desc = computed(() => sort.value.startsWith('-'))
  const sorted = computed(() => {
    const k = key.value
    const dir = desc.value ? -1 : 1
    return (rows.value ?? []).slice().sort((a, b) => {
      const x = (a as Record<string, unknown>)[k]
      const y = (b as Record<string, unknown>)[k]
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir
      return String(x).localeCompare(String(y)) * dir
    })
  })
  /** Click a column: numbers sort high-to-low first, text A-Z first; a second click flips it. */
  function by(k: string, numeric = true) {
    if (key.value === k) sort.value = desc.value ? k : `-${k}`
    else sort.value = numeric ? `-${k}` : k
  }
  function aria(k: string) {
    return key.value === k ? (desc.value ? 'descending' : 'ascending') : undefined
  }
  return { sorted, by, aria, key, desc }
}
