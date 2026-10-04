<script setup lang="ts">
import type { RaceDetail, RaceLaps } from '~/utils/types'
import type { Period } from '~/utils/charts'

const route = useRoute()
const year = computed(() => Number(route.params.year))
const round = computed(() => Number(route.params.round))
const { data, error } = await useApi<RaceDetail>(() => `/races/${year.value}/${round.value}`)
notFoundIf(error, 'Race')

const race = computed(() => data.value?.race)
const rawView = useQueryState('view', 'results')
// Older links used "times" and "stints"; they now open Pace and Strategy.
const view = computed({
  get: () => ({ times: 'pace', stints: 'strategy' })[rawView.value] ?? rawView.value,
  set: (v: string) => (rawView.value = v),
})
const focusParam = useQueryState('focus', '')
const reference = useQueryState('ref', 'leader')
const pickedParam = useQueryState('drivers', '')

const LAP_VIEWS = ['story', 'laps', 'gaps']
const tabs = computed(() => {
  const t = [{ id: 'results', label: 'Results' }]
  if (data.value?.has_laps) {
    t.push({ id: 'story', label: 'Story' }, { id: 'laps', label: 'Lap chart' }, { id: 'gaps', label: 'Gaps' }, { id: 'pace', label: 'Pace' })
  }
  // From 2018 the timing data has tyres even before the lap-by-lap dump and the pit stop list include a race.
  const timed = (data.value?.race.year ?? 0) >= 2018 && !!data.value?.results.length
  if (data.value?.has_laps || data.value?.pit_stops.length || timed) t.push({ id: 'strategy', label: 'Strategy' })
  if ((data.value?.race.year ?? 0) >= 2018) t.push({ id: 'telemetry', label: 'Telemetry' })
  if (data.value?.pit_stops.length) t.push({ id: 'pits', label: 'Pit stops' })
  if (data.value?.qualifying.length) t.push({ id: 'qualifying', label: 'Qualifying' })
  if (data.value?.sprint.length) t.push({ id: 'sprint', label: 'Sprint' })
  return t
})

const { data: laps, execute: loadLaps, status: lapStatus } = useFetch<RaceLaps>(() => `/api/races/${year.value}/${round.value}/laps`, {
  immediate: false,
  server: false,
  key: `laps:${year.value}:${round.value}`,
})
watch(
  view,
  (v) => {
    if (import.meta.client && LAP_VIEWS.includes(v) && !laps.value && data.value?.has_laps) loadLaps()
  },
  { immediate: true },
)
onMounted(() => {
  if (LAP_VIEWS.includes(view.value) && !laps.value && data.value?.has_laps) loadLaps()
})

const explicitFocus = computed(() => focusParam.value.split(',').filter(Boolean))
// With 20 lines the gap chart is unreadable, so it starts on the top six finishers until the visitor picks.
const focus = computed(() =>
  explicitFocus.value.length || view.value !== 'gaps' ? explicitFocus.value : (laps.value?.drivers.slice(0, 6).map((d) => d.driver_id) ?? []),
)
function toggleFocus(id: string) {
  const set = new Set(focus.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  focusParam.value = [...set].join(',')
}

const picked = computed(() => {
  const p = pickedParam.value.split(',').filter(Boolean)
  return p.length ? p.slice(0, 4) : (data.value?.results.filter((r) => r.position).slice(0, 3).map((r) => r.driver_id) ?? [])
})
function togglePicked(id: string) {
  const set = new Set(picked.value)
  if (set.has(id)) set.delete(id)
  else if (set.size < 4) set.add(id)
  pickedParam.value = [...set].join(',')
}

const referenceOptions = computed(() => [
  { value: 'leader', label: 'Race leader', sub: 'Whoever led each lap' },
  ...(laps.value?.drivers ?? []).map((d) => ({
    value: d.driver_id,
    label: d.driver,
    sub: d.constructor,
    swatch: teamColor(d.constructor_id),
    group: 'Drivers',
  })),
])

const { data: storyPeriods } = useFetch<{ periods: Period[] }>(() => `/api/races/${year.value}/${round.value}/story`, {
  server: false,
  key: `story:${year.value}:${round.value}`,
  immediate: false,
})
watch(
  view,
  (v) => {
    if (import.meta.client && ['laps', 'gaps'].includes(v) && !storyPeriods.value) refreshNuxtData(`story:${year.value}:${round.value}`)
  },
  { immediate: true },
)
const lapChart = useChartOption(() => (laps.value ? withLapMarks(lapChartOption(laps.value, focus.value), storyPeriods.value?.periods) : {}))
const gapChart = useChartOption(() =>
  laps.value ? withLapMarks(gapChartOption(laps.value, reference.value, focus.value), storyPeriods.value?.periods) : {},
)
const driverNames = computed(() => Object.fromEntries((data.value?.results ?? []).map((r) => [r.driver_id, r.driver])))
const slopeChart = useChartOption(() =>
  slopeOption(
    (data.value?.results ?? []).map((r) => ({ driver_id: r.driver_id, abbreviation: r.abbreviation || r.driver, constructor_id: r.constructor_id, grid: r.grid, position: r.position })),
  ),
)

const winner = computed(() => data.value?.results.find((r) => r.position === 1))
const pole = computed(() => data.value?.qualifying.find((q) => q.position === 1))
const fastest = computed(() => data.value?.fastest_laps[0])
const finishers = computed(() => data.value?.results.filter((r) => r.position).length ?? 0)
const starters = computed(() => data.value?.results.filter((r) => !['DNQ', 'DNPQ', 'DNS', 'DNP', 'EX'].includes(r.position_text)).length ?? 0)
const biggestGain = computed(() =>
  (data.value?.results ?? [])
    .filter((r) => r.position && r.grid)
    .map((r) => ({ ...r, gain: r.grid! - r.position! }))
    .sort((a, b) => b.gain - a.gain)[0],
)

const pitRanking = computed(() =>
  (data.value?.pit_stops ?? []).filter((p) => p.duration_ms).slice().sort((a, b) => a.duration_ms! - b.duration_ms!),
)
const pole_ms = computed(() => {
  const q = pole.value
  if (!q) return null
  return q.time_millis
})
function qualiBest(q: RaceDetail['qualifying'][number]) {
  return q.q3 || q.q2 || q.q1 || q.time
}

usePageMeta({
  title: () => (race.value ? `${race.value.year} ${race.value.grand_prix}` : 'Race'),
  description: () =>
    race.value && winner.value
      ? `${race.value.year} ${race.value.grand_prix} at ${race.value.circuit}: won by ${winner.value.driver} (${winner.value.constructor}). Results, lap chart, gaps, lap times and pit stops.`
      : undefined,
  eyebrow: () => (race.value ? `Round ${race.value.round} · ${date(race.value.date, { dateStyle: 'long' })}` : undefined),
  stats: () => [
    ['Winner', winner.value?.driver],
    ['Pole', pole.value?.driver],
    ['Fastest lap', fastest.value?.time],
    ['Finishers', data.value?.results.length ? `${finishers.value}/${starters.value}` : null],
  ],
  color: () => (winner.value ? teamColor(winner.value.constructor_id) : undefined),
})
</script>

<template>
  <div v-if="data && race">
    <PageHeader
      :title="`${race.year} ${race.grand_prix}`"
      :crumbs="[{ to: '/seasons', label: 'Seasons' }, { to: `/seasons/${race.year}`, label: String(race.year) }, { label: `Round ${race.round} · ${date(race.date, { dateStyle: 'long' })}` }]"
    >
      <template #sub>
        <NuxtLink :to="`/circuits/${race.circuit_id}`" class="link">{{ race.circuit }}</NuxtLink>, {{ race.place_name }}, {{ race.country }}
        <span v-if="race.laps" class="muted"> · {{ race.laps }} laps<template v-if="race.distance">, {{ num(race.distance, 1) }} km</template></span>
      </template>
      <NuxtLink v-if="data.prev" class="btn" :to="`/races/${data.prev.year}/${data.prev.round}`" :title="data.prev.grand_prix"><Icon name="left" :size="16" /> Previous race</NuxtLink>
      <NuxtLink v-if="data.next" class="btn" :to="`/races/${data.next.year}/${data.next.round}`" :title="data.next.grand_prix">Next race <Icon name="right" :size="16" /></NuxtLink>
    </PageHeader>

    <div v-if="!data.results.length" class="panel empty">
      This race has not been run yet.
      <svg v-if="race.layout_path" viewBox="0 0 500 500" class="layout big"><path :d="race.layout_path" /></svg>
    </div>

    <div v-else class="stack">
      <div class="summary">
        <Tiles class="grow">
          <StatTile label="Winner" :value="winner?.driver" :hint="winner ? `${winner.constructor} · from P${winner.grid ?? '?'}` : ''" :to="winner ? `/drivers/${winner.driver_id}` : undefined" />
          <StatTile v-if="pole" label="Pole position" :value="pole.driver" :hint="qualiBest(pole) ?? ''" :to="`/drivers/${pole.driver_id}`" />
          <StatTile v-if="fastest" label="Fastest lap" :value="fastest.driver" :hint="`${fastest.time}${fastest.lap ? ` · lap ${fastest.lap}` : ''}`" :to="`/drivers/${fastest.driver_id}`" />
          <StatTile label="Finishers" :value="`${finishers}/${starters}`" :hint="biggestGain && biggestGain.gain > 0 ? `Best climb: ${biggestGain.driver} +${biggestGain.gain}` : ''" />
        </Tiles>
        <NuxtLink v-if="race.layout_path" :to="`/circuits/${race.circuit_id}`" class="layout-card" :title="`${race.circuit} layout`">
          <svg viewBox="0 0 500 500" class="layout"><path :d="race.layout_path" /></svg>
        </NuxtLink>
      </div>

      <Tabs v-model="view" :tabs="tabs" label="Race views" />

      <!-- Results -->
      <template v-if="view === 'results'">
        <div class="grid-12">
          <Panel class="span-8" title="Race result" flush>
            <div class="table-scroll">
              <table class="data">
                <thead>
                  <tr><th class="c">Pos</th><th>Driver</th><th class="hide-sm">Team</th><th class="r hide-md">Laps</th><th class="r">Time / gap</th><th class="r hide-sm">Grid</th><th class="r">Pts</th></tr>
                </thead>
                <tbody>
                  <tr v-for="r in data.results" :key="r.driver_id">
                    <td class="c"><ResultPos :position="r.position" :text="r.position_text" /></td>
                    <td class="nowrap">
                      <NuxtLink :to="`/drivers/${r.driver_id}`"><b>{{ r.driver }}</b></NuxtLink>
                      <span v-if="r.fastest_lap" class="badge" title="Fastest lap" style="margin-left: 6px">FL</span>
                      <span v-if="r.driver_of_the_day" class="badge" title="Driver of the day" style="margin-left: 4px">DotD</span>
                      <span class="sub-line only-sm"><TeamName :id="r.constructor_id" :name="r.constructor" :link="false" /><template v-if="r.grid"> · from P{{ r.grid }}</template></span>
                    </td>
                    <td class="hide-sm"><TeamName :id="r.constructor_id" :name="r.constructor" /></td>
                    <td class="r hide-md">{{ r.laps ?? '' }}</td>
                    <td class="r nowrap">
                      <template v-if="r.position === 1">{{ r.time }}</template>
                      <template v-else-if="r.position">{{ r.gap ?? (r.gap_laps ? `+${r.gap_laps} lap${r.gap_laps > 1 ? 's' : ''}` : '') }}</template>
                      <span v-else class="muted small ret">{{ r.reason_retired ?? r.position_text }}</span>
                    </td>
                    <td class="r hide-sm nowrap">
                      {{ r.grid ?? '' }}
                      <span v-if="r.position && r.grid && r.grid !== r.position" class="tiny" :class="r.grid > r.position ? 'up' : 'down'">
                        {{ r.grid > r.position ? '▲' : '▼' }}{{ Math.abs(r.grid - r.position) }}
                      </span>
                    </td>
                    <td class="r"><b v-if="r.points">{{ points(r.points) }}</b></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Panel>
          <div class="span-4 stack">
            <Panel title="Grid to finish" note="Classified drivers. Hover or tap a line for the change.">
              <Chart :option="slopeChart" :height="Math.max(320, finishers * 22)" :compact-height="Math.max(320, finishers * 20)" label="Grid position against finishing position" />
            </Panel>
            <Panel v-if="data.standings.length" title="Championship after this race" flush>
              <table class="data">
                <tbody>
                  <tr v-for="s in data.standings" :key="s.driver_id">
                    <td class="c" style="width: 44px"><ResultPos :position="s.position" /></td>
                    <td><NuxtLink :to="`/drivers/${s.driver_id}`">{{ s.driver }}</NuxtLink></td>
                    <td class="r"><b>{{ points(s.points) }}</b></td>
                  </tr>
                </tbody>
              </table>
            </Panel>
          </div>
        </div>
      </template>

      <!-- Lap-based views -->
      <template v-else-if="LAP_VIEWS.includes(view)">
        <div v-if="!laps" class="panel"><div class="skeleton" style="height: 480px" /></div>
        <template v-else>
          <RaceStory v-if="view === 'story'" :year="year" :round="round" :laps="laps" />
          <Panel v-if="view === 'laps'" title="Lap chart" note="Position at the end of every lap; lap 0 is the starting grid. Dots mark pit stops. Pick drivers below to highlight them.">
            <Chart :option="lapChart" :height="Math.max(460, laps.drivers.length * 26)" :compact-height="Math.max(420, laps.drivers.length * 22)" label="Position by lap for every driver" share-id="lap-chart" />
          </Panel>
          <Panel v-if="view === 'gaps'" title="Gaps" note="Seconds behind the reference at the end of each lap; dots mark pit stops. Starts on the top six finishers, pick others below.">
            <template #actions>
              <UiSelect v-model="reference" label="Gap to" :options="referenceOptions" searchable />
            </template>
            <Chart :option="gapChart" :height="520" :compact-height="420" label="Gap to the reference driver by lap" share-id="gaps" />
          </Panel>
          <div v-if="view !== 'story'" class="pickers panel">
            <div class="spread">
              <span class="small"><b>Highlight drivers</b> <span class="muted">tap to add or remove</span></span>
              <button v-if="explicitFocus.length" class="btn ghost" @click="focusParam = ''">Show all</button>
            </div>
            <div class="chips">
            <button
              v-for="d in laps.drivers"
              :key="d.driver_id"
              class="chip pick"
              :aria-pressed="focus.includes(d.driver_id)"
              :title="d.driver"
              :class="{ on: focus.includes(d.driver_id) }"
              @click="toggleFocus(d.driver_id)"
            >
              <span class="swatch" :style="{ background: teamColor(d.constructor_id) }" />
              {{ d.abbreviation || d.driver }}
            </button>
            </div>
          </div>
        </template>
        <p v-if="lapStatus === 'error'" class="empty">Lap data could not be loaded.</p>
      </template>

      <!-- Pace and strategy -->
      <template v-else-if="view === 'pace'">
        <RacePace :year="year" :round="round" :drivers="picked" :names="driverNames" />
        <div class="pickers panel">
          <div class="spread">
            <span class="small"><b>Drivers</b> <span class="muted">up to four</span></span>
          </div>
          <div class="chips">
            <button
              v-for="r in data.results.filter((x) => x.laps)"
              :key="r.driver_id"
              class="chip pick"
              :class="{ on: picked.includes(r.driver_id) }"
              :aria-pressed="picked.includes(r.driver_id)"
              :title="r.driver"
              @click="togglePicked(r.driver_id)"
            >
              <span class="swatch" :style="{ background: picked.includes(r.driver_id) ? seriesVar(picked.indexOf(r.driver_id) + 1) : teamColor(r.constructor_id) }" />
              {{ r.abbreviation || r.driver }}
            </button>
          </div>
        </div>
      </template>
      <RaceStrategy v-else-if="view === 'strategy'" :year="year" :round="round" :circuit-id="race.circuit_id" />
      <RaceTelemetry v-else-if="view === 'telemetry'" :year="year" :round="round" />

      <!-- Pit stops -->
      <Panel v-else-if="view === 'pits'" title="Pit stops" note="Time in the pit lane, from entry to exit, fastest first." flush>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th class="r">#</th><th>Driver</th><th class="hide-sm">Team</th><th class="r hide-sm">Stop</th><th class="r">Lap</th><th class="r">Pit lane</th></tr></thead>
            <tbody>
              <tr v-for="(p, i) in pitRanking" :key="`${p.driver_id}-${p.stop}`">
                <td class="r muted">{{ i + 1 }}</td>
                <td><NuxtLink :to="`/drivers/${p.driver_id}`">{{ p.driver }}</NuxtLink><span class="sub-line only-sm">{{ p.constructor }} · stop {{ p.stop }}</span></td>
                <td class="hide-sm"><TeamName :id="p.constructor_id" :name="p.constructor" /></td>
                <td class="r hide-sm">{{ p.stop }}</td>
                <td class="r">{{ p.lap }}</td>
                <td class="r"><b>{{ lapTime(p.duration_ms) }}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <!-- Qualifying -->
      <div v-else-if="view === 'qualifying'" class="stack">
      <RaceQualiAnalysis v-if="race.year >= 2018" :year="year" :round="round" />
      <Panel title="Qualifying" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr>
                <th class="c">Pos</th><th>Driver</th><th class="hide-sm">Team</th>
                <template v-if="race.qualifying_format === 'KNOCKOUT'"><th class="r hide-sm">Q1</th><th class="r hide-sm">Q2</th><th class="r">Best</th></template>
                <th v-else class="r">Time</th>
                <th class="r">Gap to pole</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in data.qualifying" :key="q.driver_id">
                <td class="c"><ResultPos :position="q.position" :text="q.position_text" /></td>
                <td>
                  <NuxtLink :to="`/drivers/${q.driver_id}`"><b>{{ q.driver }}</b></NuxtLink>
                  <span class="sub-line only-sm">{{ q.constructor }}</span>
                </td>
                <td class="hide-sm"><TeamName :id="q.constructor_id" :name="q.constructor" /></td>
                <template v-if="race.qualifying_format === 'KNOCKOUT'">
                  <td class="r hide-sm">{{ q.q1 ?? '' }}</td><td class="r hide-sm">{{ q.q2 ?? '' }}</td>
                  <td class="r"><b>{{ q.q3 ?? q.q2 ?? q.q1 ?? '' }}</b><span v-if="!q.q3 && (q.q2 || q.q1)" class="sub-line">{{ q.q2 ? 'Q2' : 'Q1' }}</span></td>
                </template>
                <td v-else class="r">{{ q.time ?? '' }}</td>
                <td class="r muted">{{ q.position === 1 ? '' : q.gap ?? (q.time_millis && pole_ms ? gapSeconds(q.time_millis - pole_ms) : '') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
      </div>

      <!-- Sprint -->
      <Panel v-else-if="view === 'sprint'" title="Sprint" flush>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th class="c">Pos</th><th>Driver</th><th class="hide-sm">Team</th><th class="r hide-md">Laps</th><th class="r">Time / gap</th><th class="r hide-sm">Grid</th><th class="r">Pts</th></tr></thead>
            <tbody>
              <tr v-for="r in data.sprint" :key="r.driver_id">
                <td class="c"><ResultPos :position="r.position" :text="r.position_text" /></td>
                <td><NuxtLink :to="`/drivers/${r.driver_id}`"><b>{{ r.driver }}</b></NuxtLink><span class="sub-line only-sm">{{ r.constructor }}</span></td>
                <td class="hide-sm"><TeamName :id="r.constructor_id" :name="r.constructor" /></td>
                <td class="r hide-md">{{ r.laps }}</td>
                <td class="r">{{ r.position === 1 ? r.time : r.position ? r.gap : r.reason_retired }}</td>
                <td class="r hide-sm">{{ r.grid ?? '' }}</td>
                <td class="r"><b v-if="r.points">{{ points(r.points) }}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.summary {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.layout-card {
  flex: none;
  width: 132px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  padding: 10px;
}
.layout-card:hover {
  border-color: var(--accent);
}
.layout {
  width: 100%;
  height: 100%;
  max-height: 110px;
}
.layout path,
.big path {
  fill: none;
  stroke: var(--ink);
  stroke-width: 14;
  stroke-linejoin: round;
}
.layout.big {
  display: block;
  margin: 24px auto 0;
  max-width: 280px;
}
@media (max-width: 900px) {
  .layout-card {
    display: none;
  }
}
.pickers {
  gap: 10px;
}
.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.pick {
  min-width: 64px;
  justify-content: flex-start;
}
.ret {
  white-space: normal;
}
@media (max-width: 640px) {
  .pick {
    min-width: 0;
    flex: 1 1 calc(25% - 6px);
    height: 34px;
  }
}
.up { color: var(--good-ink); }
.down { color: var(--bad); }
</style>
