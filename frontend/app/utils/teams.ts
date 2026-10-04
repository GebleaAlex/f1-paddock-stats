// Team colours. Colour values are facts about liveries, not artwork; no logos are used anywhere.
// In race and season charts a driver is drawn in their team's colour, and the team's second driver gets a dashed
// line, the convention fans already know. Both are backed by direct labels and tooltips, so identity never rests on
// colour alone. Comparisons of up to four chosen drivers use the validated categorical series instead (seriesColor).

const TEAM_COLORS: Record<string, string> = {
  ferrari: '#dc0000',
  mclaren: '#ff8000',
  mercedes: '#00b8a0',
  'red-bull': '#3671c6',
  williams: '#1868db',
  'aston-martin': '#229971',
  alpine: '#0093cc',
  haas: '#8e9196',
  sauber: '#9b0000',
  'kick-sauber': '#2fbf24',
  audi: '#bb1d1d',
  cadillac: '#7a7a7d',
  rb: '#6692ff',
  'racing-bulls': '#6692ff',
  alphatauri: '#4e7c9b',
  'toro-rosso': '#469bff',
  'alfa-romeo': '#a50f2d',
  'racing-point': '#f596c8',
  'force-india': '#f596c8',
  renault: '#e6b800',
  'lotus-f1': '#b6ba00',
  lotus: '#1e6b37',
  'lotus-racing': '#1e6b37',
  brabham: '#2b4c9c',
  tyrrell: '#0b3d91',
  benetton: '#00a651',
  jordan: '#e8b400',
  brm: '#3a6b35',
  cooper: '#0b5d1e',
  maserati: '#b5121b',
  ligier: '#1a5fb4',
  arrows: '#e07b00',
  minardi: '#3c3c3c',
  toyota: '#c8102e',
  honda: '#c0c0c0',
  bar: '#b8b8b8',
  'bmw-sauber': '#4f86c6',
  brawn: '#b8d300',
  jaguar: '#0d5d36',
  stewart: '#ffffff',
  march: '#e2001a',
  matra: '#1a3d8f',
  vanwall: '#1d5e3b',
  surtees: '#d9d9d9',
  shadow: '#2a2a2a',
  footwork: '#e05c00',
  prost: '#1e40af',
  'super-aguri': '#d22630',
  marussia: '#6e0000',
  manor: '#0d7fd1',
  caterham: '#00602b',
  hrt: '#a08c5b',
  virgin: '#c82e37',
  spyker: '#ff6600',
  midland: '#c41e3a',
}

const FALLBACK = ['#6b7280', '#8b5cf6', '#0891b2', '#b45309', '#be185d', '#4d7c0f', '#7c3aed', '#0f766e']

function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

export function teamColor(constructorId: string | null | undefined): string {
  if (!constructorId) return '#8a8a8a'
  return TEAM_COLORS[constructorId] ?? FALLBACK[hash(constructorId) % FALLBACK.length]!
}

/** Resolved value of a CSS custom property (charts need real colours, SVG attributes cannot use var()). */
export function cssVar(name: string, fallback = '#888'): string {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** Categorical slot as a CSS variable, for templates (renders the same on the server and in the browser). */
export function seriesVar(slot: number): string {
  return `var(--series-${((slot - 1) % 8) + 1})`
}

/** Categorical slot colour (1-based), read from the CSS tokens so it follows the theme. For chart options only. */
export function seriesColor(slot: number): string {
  const name = `--series-${((slot - 1) % 8) + 1}`
  if (typeof window === 'undefined') return ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'][(slot - 1) % 4]!
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#2a78d6'
}

export interface Styled {
  driver_id: string
  constructor_id: string
}

/** Colour and dash per driver: team colour, dashed for the team's second driver in the list. */
export function driverStyles<T extends Styled>(drivers: T[]): Record<string, { color: string; dashed: boolean }> {
  const seen: Record<string, number> = {}
  const out: Record<string, { color: string; dashed: boolean }> = {}
  for (const d of drivers) {
    const n = (seen[d.constructor_id] = (seen[d.constructor_id] ?? 0) + 1)
    out[d.driver_id] = { color: teamColor(d.constructor_id), dashed: n > 1 }
  }
  return out
}
