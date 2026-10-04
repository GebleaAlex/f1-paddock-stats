// Formatting helpers shared by pages and charts.

export function lapTime(ms: number | null | undefined): string {
  if (ms == null) return '–'
  const total = ms / 1000
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const sec = s.toFixed(3).padStart(6, '0')
  if (h) return `${h}:${String(m).padStart(2, '0')}:${sec}`
  return m ? `${m}:${sec}` : s.toFixed(3)
}

export function gapSeconds(ms: number | null | undefined, digits = 3): string {
  if (ms == null) return '–'
  const s = ms / 1000
  return `${s >= 0 ? '+' : '−'}${Math.abs(s).toFixed(digits)}s`
}

export function pct(value: number | null | undefined, digits = 3, signed = true): string {
  if (value == null) return '–'
  const sign = signed ? (value > 0 ? '+' : value < 0 ? '−' : '') : ''
  return `${sign}${Math.abs(value).toFixed(digits)}%`
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value == null) return '–'
  return value.toLocaleString('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function points(value: number | null | undefined): string {
  if (value == null) return '–'
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '')
}

export function ordinal(n: number | null | undefined): string {
  if (n == null) return '–'
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]!)
}

export function date(value: string | null | undefined, opts: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }): string {
  if (!value) return '–'
  return new Date(`${value}T12:00:00Z`).toLocaleDateString('en-GB', { timeZone: 'UTC', ...opts })
}

export function age(born: string | null | undefined, at?: string | null): number | null {
  if (!born) return null
  const b = new Date(born)
  const a = at ? new Date(at) : new Date()
  let years = a.getUTCFullYear() - b.getUTCFullYear()
  if (a.getUTCMonth() < b.getUTCMonth() || (a.getUTCMonth() === b.getUTCMonth() && a.getUTCDate() < b.getUTCDate()))
    years--
  return years
}

export function years(first: number | null | undefined, last: number | null | undefined): string {
  if (!first) return '–'
  return !last || last === first ? String(first) : `${first}–${last}`
}

export function share(a: number, b: number): number | null {
  return a + b > 0 ? a / (a + b) : null
}

/** "1, 2, 3" style list joined with "and". */
export function listing(items: string[]): string {
  if (items.length < 2) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
