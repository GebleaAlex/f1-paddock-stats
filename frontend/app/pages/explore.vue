<script setup lang="ts">
// Stat explorer: race results filtered by years, circuit, team, driver, teammate, starting position and starting
// tyre, grouped by driver, team, season or circuit. Every filter lives in the URL, so every answer is a link.
interface Row {
  key: string
  name: string
  href: string
  races: number
  wins: number
  podiums: number
  poles: number
  points: number
  avg_finish: number | null
  avg_grid: number | null
  avg_gained: number | null
  dnfs: number
  best_finish: number | null
  win_rate: number
  first_year: number
  last_year: number
}
interface Result {
  rows: Row[]
  total: { entries: number; races: number }
}

usePageMeta({ title: 'Stat explorer', description: 'Ask your own questions of every Formula 1 result since 1950 and share the answer as a link.' })

const group = useQueryState('group', 'driver')
const from = useQueryState('from', '1950')
const to = useQueryState('to', String(new Date().getFullYear()))
const circuit = useQueryState('circuit', '')
const team = useQueryState('constructor', '')
const driver = useQueryState('driver', '')
const teammate = useQueryState('teammate', '')
const grid = useQueryState('grid', 'any')
const tyre = useQueryState('tyre', '')
const minRaces = useQueryState('min', '1')
const sort = useQueryState('sort', 'wins')

const { data: circuits } = useApi<{ id: string; name: string; place_name: string; country: string; races: number }[]>('/circuits', { lazy: true, server: false })
const { data: teams } = useApi<{ id: string; name: string; first_year: number | null; last_year: number | null; wins: number }[]>('/constructors', { lazy: true, server: false })
const { data: driverList } = useApi<{ id: string; name: string; first_year: number | null; last_year: number | null; starts: number }[]>('/drivers', { lazy: true, server: false })

const thisYear = new Date().getFullYear()
const yearOptions = Array.from({ length: thisYear - 1949 }, (_, i) => String(thisYear - i)).map((y) => ({ value: y, label: y }))
const GROUPS = [
  { value: 'driver', label: 'Driver' },
  { value: 'constructor', label: 'Team' },
  { value: 'season', label: 'Season' },
  { value: 'circuit', label: 'Circuit' },
  { value: 'driver_season', label: 'Driver and season' },
]
const GRIDS: Record<string, { label: string; min?: number; max?: number }> = {
  any: { label: 'Anywhere' },
  pole: { label: 'Pole', min: 1, max: 1 },
  front: { label: 'Front row', min: 1, max: 2 },
  top3: { label: 'Top 3', min: 1, max: 3 },
  top10: { label: 'Top 10', min: 1, max: 10 },
  outside3: { label: 'Outside the top 3', min: 4 },
  outside10: { label: 'Outside the top 10', min: 11 },
  back: { label: 'Back of the grid (P16+)', min: 16 },
}
const SORTS = [
  { value: 'wins', label: 'Wins' },
  { value: 'podiums', label: 'Podiums' },
  { value: 'poles', label: 'Poles' },
  { value: 'points', label: 'Points' },
  { value: 'races', label: 'Races' },
  { value: 'win_rate', label: 'Win rate' },
  { value: 'avg_finish', label: 'Average finish' },
  { value: 'gained', label: 'Places gained' },
  { value: 'dnfs', label: 'Retirements' },
]
const TYRES = [
  { value: '', label: 'Any', sub: 'All years' },
  ...['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'].map((c) => ({ value: c, label: compound(c).label, sub: '2018 onwards', swatch: compound(c).color })),
]
const MINS = ['1', '5', '10', '25', '50', '100'].map((m) => ({ value: m, label: m === '1' ? 'Any' : `${m}+ races` }))

const any = { value: '', label: 'Any' }
const circuitOptions = computed(() => [any, ...(circuits.value ?? []).map((c) => ({ value: c.id, label: c.name, sub: `${c.place_name}, ${c.country} · ${c.races} races` }))])
const teamOptions = computed(() => [any, ...(teams.value ?? []).map((t) => ({ value: t.id, label: t.name, sub: years(t.first_year, t.last_year), swatch: teamColor(t.id) }))])
const driverOptions = computed(() => [
  any,
  ...(driverList.value ?? []).filter((d) => d.starts > 0).map((d) => ({ value: d.id, label: d.name, sub: years(d.first_year, d.last_year) })),
])

const url = computed(() => {
  const g = GRIDS[grid.value] ?? GRIDS.any!
  const q = new URLSearchParams({ group: group.value, from: from.value, to: to.value, sort: sort.value, min_races: minRaces.value, limit: '100' })
  if (circuit.value) q.set('circuit', circuit.value)
  if (team.value) q.set('constructor', team.value)
  if (driver.value) q.set('driver', driver.value)
  if (teammate.value) q.set('teammate', teammate.value)
  if (g.min) q.set('grid_min', String(g.min))
  if (g.max) q.set('grid_max', String(g.max))
  if (tyre.value) q.set('start_tyre', tyre.value)
  return `/explore?${q}`
})
const { data, pending, error } = await useApi<Result>(() => url.value)

// While the option lists load, fall back to a readable version of the id ("monaco" -> "Monaco").
const label = (opts: { value: string; label: string }[], v: string) =>
  opts.find((o) => o.value === v)?.label ?? v.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase())
const sentence = computed(() => {
  const parts: string[] = [`${label(GROUPS, group.value)} totals`]
  if (driver.value) parts.push(`for ${label(driverOptions.value, driver.value)}`)
  if (team.value) parts.push(`at ${label(teamOptions.value, team.value)}`)
  if (teammate.value) parts.push(`as teammates of ${label(driverOptions.value, teammate.value)}`)
  if (circuit.value) parts.push(`at ${label(circuitOptions.value, circuit.value)}`)
  if (grid.value !== 'any') parts.push(`starting ${GRIDS[grid.value]!.label.toLowerCase().replace('pole', 'from pole')}`)
  if (tyre.value) parts.push(`on ${compound(tyre.value).label.toLowerCase()} tyres at the start`)
  parts.push(from.value === to.value ? `in ${from.value}` : `from ${from.value} to ${to.value}`)
  return parts.join(' ')
})

const EXAMPLES = [
  { label: 'Monaco wins from outside the top 3', q: '?circuit=monaco&grid=outside3' },
  { label: 'Most wins from the back of the grid', q: '?grid=back' },
  { label: "Hamilton's teammates", q: '?teammate=lewis-hamilton&sort=races' },
  { label: 'Ferrari drivers in the 2000s', q: '?constructor=ferrari&from=2000&to=2009' },
  { label: 'Best seasons by win rate', q: '?group=driver_season&sort=win_rate&min=10' },
  { label: 'Wins after starting on hard tyres', q: '?tyre=HARD&from=2018' },
]
// Phones show the four main controls; the rest fold away behind "More filters".
const moreOpen = ref(false)
const activeFilters = computed(
  () => [circuit.value, team.value, driver.value, teammate.value, tyre.value].filter(Boolean).length + (grid.value !== 'any' ? 1 : 0) + (minRaces.value !== '1' ? 1 : 0),
)
function reset() {
  navigateTo('/explore')
}
const copied = ref(false)
async function copy() {
  await navigator.clipboard.writeText(location.href)
  copied.value = true
  setTimeout(() => (copied.value = false), 1600)
}
</script>

<template>
  <div>
    <PageHeader title="Stat explorer" sub="Filter every race result since 1950 and group it your way. The link always reproduces the answer.">
      <button class="btn" type="button" @click="copy"><Icon :name="copied ? 'check' : 'link'" :size="16" /> {{ copied ? 'Link copied' : 'Copy link' }}</button>
    </PageHeader>

    <section class="panel builder">
      <div class="controls" :class="{ open: moreOpen }">
        <UiSelect v-model="group" label="Group by" :options="GROUPS" block />
        <UiSelect v-model="sort" label="Sort by" :options="SORTS" block />
        <UiSelect v-model="from" label="From" :options="yearOptions" block />
        <UiSelect v-model="to" label="To" :options="yearOptions" block />
        <UiSelect v-model="circuit" class="more" label="Circuit" :options="circuitOptions" searchable block />
        <UiSelect v-model="team" class="more" label="Team" :options="teamOptions" searchable block />
        <UiSelect v-model="driver" class="more" label="Driver" :options="driverOptions" searchable block />
        <UiSelect v-model="teammate" class="more" label="Teammate of" :options="driverOptions" searchable block />
        <UiSelect v-model="grid" class="more" label="Started" :options="Object.entries(GRIDS).map(([value, g]) => ({ value, label: g.label }))" block />
        <UiSelect v-model="tyre" class="more" label="Starting tyre" :options="TYRES" block />
        <UiSelect v-model="minRaces" class="more" label="At least" :options="MINS" block />
        <button class="btn ghost more" type="button" @click="reset">Clear all</button>
      </div>
      <button class="btn more-toggle" type="button" :aria-expanded="moreOpen" @click="moreOpen = !moreOpen">
        {{ moreOpen ? 'Fewer filters' : `More filters${activeFilters ? ` (${activeFilters} on)` : ''}` }}
      </button>
      <div class="examples">
        <span class="small muted">Try:</span>
        <NuxtLink v-for="e in EXAMPLES" :key="e.q" :to="`/explore${e.q}`" class="chip">{{ e.label }}</NuxtLink>
      </div>
    </section>

    <Panel class="results" :title="sentence" :note="data ? `${num(data.total.entries)} race entries in ${num(data.total.races)} races match. ${data.rows.length === 100 ? 'Showing the top 100.' : ''}` : ''" flush>
      <div class="table-scroll" :class="{ dim: pending }">
        <table v-if="data?.rows.length" class="data">
          <thead>
            <tr>
              <th class="r">#</th><th>{{ label(GROUPS, group) }}</th><th class="r">Races</th><th class="r">Wins</th>
              <th class="r hide-sm">Podiums</th><th class="r hide-sm">Poles</th><th class="r hide-md">Points</th>
              <th class="r hide-sm">Win rate</th><th class="r hide-md">Avg finish</th><th class="r hide-md">Places gained</th><th class="r hide-md">Retired</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in data.rows" :key="r.key">
              <td class="r muted">{{ i + 1 }}</td>
              <td>
                <NuxtLink :to="r.href"><b>{{ r.name }}</b></NuxtLink>
                <span v-if="group !== 'season' && group !== 'driver_season'" class="sub-line">{{ years(r.first_year, r.last_year) }}</span>
              </td>
              <td class="r">{{ r.races }}</td>
              <td class="r strong-cell">{{ r.wins || '' }}</td>
              <td class="r hide-sm">{{ r.podiums || '' }}</td>
              <td class="r hide-sm">{{ r.poles || '' }}</td>
              <td class="r hide-md">{{ r.points ? points(r.points) : '' }}</td>
              <td class="r hide-sm">{{ r.win_rate ? `${r.win_rate}%` : '' }}</td>
              <td class="r hide-md">{{ r.avg_finish ?? '–' }}</td>
              <td class="r hide-md">{{ r.avg_gained != null ? (r.avg_gained > 0 ? `+${r.avg_gained}` : r.avg_gained) : '–' }}</td>
              <td class="r hide-md">{{ r.dnfs || '' }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else-if="!pending" :title="error ? 'That query did not work' : 'Nothing matches'" :text="error ? 'Check the filters, or clear them and start again.' : 'Widen the years or remove a filter.'" />
      </div>
    </Panel>
  </div>
</template>

<style scoped>
.builder {
  margin-bottom: var(--gap);
}
.controls {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
  gap: 8px;
  align-items: center;
}
.more-toggle {
  display: none;
}
@media (max-width: 640px) {
  .controls .more {
    display: none;
  }
  .controls.open .more {
    display: block;
  }
  .more-toggle {
    display: inline-flex;
    width: 100%;
  }
}
.examples {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.dim {
  opacity: 0.55;
  transition: opacity 0.15s;
}
</style>
