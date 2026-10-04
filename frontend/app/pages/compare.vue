<script setup lang="ts">
import type { EChartsOption, SeriesOption } from 'echarts'
import type { DriverTotals } from '~/utils/types'

interface CompareDriver {
  driver: DriverTotals & { id: string; name: string; abbreviation: string | null; date_of_birth: string | null; first_year: number; last_year: number }
  starts: { year: number; round: number; abbreviation: string; age: number; position: number | null; grid: number | null; wins: number; podiums: number; poles: number; points: number }[]
  seasons: { year: number; position: number | null }[]
}
interface CompareResponse {
  drivers: CompareDriver[]
  teammate_pairs: { driver_a: string; driver_b: string; races: number; quali_won: number; quali_lost: number; race_won: number; race_lost: number }[]
}
interface Hit { type: string; id: string; name: string; sub: string | null }

const ids = useQueryState('drivers', '')
const list = computed(() => ids.value.split(',').filter(Boolean).slice(0, 4))
const metric = useQueryState('metric', 'wins') as Ref<'wins' | 'podiums' | 'poles' | 'points'>
const axis = useQueryState('by', 'start') as Ref<'start' | 'age'>

// With no selection the request 404s; that is fine, the page shows the picker instead.
const { data } = await useApi<CompareResponse>(() => `/compare?drivers=${list.value.join(',') || '_none_'}`)
const drivers = computed(() => (list.value.length ? (data.value?.drivers ?? []) : []))

usePageMeta({
  title: () => (drivers.value.length ? drivers.value.map((d) => d.driver.name).join(' vs ') : 'Compare drivers'),
  description: 'Compare Formula 1 careers side by side: wins, podiums, poles and points by start number or by age.',
  stats: () => drivers.value.slice(0, 4).map((d) => [d.driver.name, `${d.driver.wins} wins`]),
})

// Picker
const q = ref('')
const hits = ref<Hit[]>([])
let timer: ReturnType<typeof setTimeout> | undefined
watch(q, (v) => {
  clearTimeout(timer)
  if (!v.trim()) return (hits.value = [])
  timer = setTimeout(async () => {
    hits.value = (await $fetch<Hit[]>('/api/search', { query: { q: v, limit: 8 } })).filter((h) => h.type === 'driver')
  }, 120)
})
function add(id: string) {
  if (!list.value.includes(id) && list.value.length < 4) ids.value = [...list.value, id].join(',')
  q.value = ''
  hits.value = []
}
function remove(id: string) {
  ids.value = list.value.filter((x) => x !== id).join(',')
}

const METRICS = [
  { id: 'wins', label: 'Wins' },
  { id: 'podiums', label: 'Podiums' },
  { id: 'poles', label: 'Poles' },
  { id: 'points', label: 'Points' },
] as const

const careerChart = useChartOption<EChartsOption>(() => {
  const series: SeriesOption[] = drivers.value.map((d, i) => ({
    name: d.driver.name,
    type: 'line',
    showSymbol: false,
    color: seriesColor(i + 1),
    data: d.starts.map((s, n) => [axis.value === 'age' ? s.age : n + 1, s[metric.value]]),
    endLabel: { show: true, formatter: d.driver.abbreviation ?? d.driver.name, color: cssVar('--ink-2'), fontSize: 11, fontWeight: 600 },
    emphasis: { focus: 'series' },
  }))
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 56, top: 36, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => points(v as number),
      axisPointer: { type: 'line' },
    },
    xAxis: { type: 'value', name: axis.value === 'age' ? 'Age' : 'Race start', nameLocation: 'middle', nameGap: 28, min: axis.value === 'age' ? 'dataMin' : 1, minInterval: 1 },
    yAxis: { type: 'value' },
    series,
  }
})

const seasonChart = useChartOption<EChartsOption>(() => {
  const maxYears = Math.max(1, ...drivers.value.map((d) => d.seasons.length))
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 16, top: 36, bottom: 28, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '–' : ordinal(v as number)) },
    xAxis: { type: 'category', name: 'Season of career', nameLocation: 'middle', nameGap: 28, data: Array.from({ length: maxYears }, (_, i) => String(i + 1)) },
    yAxis: { type: 'value', inverse: true, min: 1, minInterval: 1, axisLabel: { formatter: (v: number) => ordinal(v) } },
    series: drivers.value.map((d, i) => ({
      name: d.driver.name,
      type: 'line',
      color: seriesColor(i + 1),
      symbolSize: 7,
      data: d.seasons.map((s) => s.position),
      connectNulls: false,
      itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 },
    })),
  }
})

const ROWS: { label: string; get: (d: CompareDriver['driver']) => number | string | null; best?: 'max' | 'min' }[] = [
  { label: 'Seasons', get: (d) => `${years(d.first_year, d.last_year)}` },
  { label: 'Starts', get: (d) => d.starts, best: 'max' },
  { label: 'World titles', get: (d) => d.championships, best: 'max' },
  { label: 'Wins', get: (d) => d.wins, best: 'max' },
  { label: 'Win rate', get: (d) => (d.starts ? +((d.wins / d.starts) * 100).toFixed(1) : null), best: 'max' },
  { label: 'Podiums', get: (d) => d.podiums, best: 'max' },
  { label: 'Podium rate', get: (d) => (d.starts ? +((d.podiums / d.starts) * 100).toFixed(1) : null), best: 'max' },
  { label: 'Poles', get: (d) => d.poles, best: 'max' },
  { label: 'Pole rate', get: (d) => (d.starts ? +((d.poles / d.starts) * 100).toFixed(1) : null), best: 'max' },
  { label: 'Fastest laps', get: (d) => d.fastest_laps, best: 'max' },
  { label: 'Grand slams', get: (d) => d.grand_slams, best: 'max' },
]
function isBest(row: (typeof ROWS)[number], value: number | string | null) {
  if (!row.best || typeof value !== 'number' || drivers.value.length < 2) return false
  const vals = drivers.value.map((d) => row.get(d.driver)).filter((v): v is number => typeof v === 'number')
  return value === (row.best === 'max' ? Math.max(...vals) : Math.min(...vals))
}
const nameOf = (id: string) => drivers.value.find((d) => d.driver.id === id)?.driver.name ?? id
const SUGGESTIONS = [
  { title: 'The greats', text: 'Senna, Prost, Schumacher and Verstappen', ids: 'ayrton-senna,alain-prost,michael-schumacher,max-verstappen' },
  { title: 'A modern rivalry', text: 'Hamilton against Vettel', ids: 'lewis-hamilton,sebastian-vettel' },
  { title: 'The early masters', text: 'Fangio, Clark and Stewart', ids: 'juan-manuel-fangio,jim-clark,jackie-stewart' },
  { title: 'Same team, same car', text: 'Senna against Prost at McLaren', ids: 'ayrton-senna,alain-prost' },
]
const activeHit = ref(0)
watch(hits, () => (activeHit.value = 0))
function pickerKey(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') activeHit.value = Math.min(activeHit.value + 1, hits.value.length - 1)
  else if (e.key === 'ArrowUp') activeHit.value = Math.max(activeHit.value - 1, 0)
  else if (e.key === 'Enter' && hits.value[activeHit.value]) add(hits.value[activeHit.value]!.id)
  else if (e.key === 'Escape') hits.value = []
  else return
  e.preventDefault()
}
</script>

<template>
  <div>
    <PageHeader title="Compare drivers" sub="Up to four careers side by side, aligned by race start or by age. The link always keeps your selection." />

    <div class="stack">
      <section class="panel picker">
        <div class="row wrap">
          <span v-for="(d, i) in drivers" :key="d.driver.id" class="chip sel">
            <span class="swatch" :style="{ background: seriesVar(i + 1) }" />
            <NuxtLink :to="`/drivers/${d.driver.id}`">{{ d.driver.name }}</NuxtLink>
            <button class="x" type="button" :aria-label="`Remove ${d.driver.name}`" @click="remove(d.driver.id)"><Icon name="close" :size="14" /></button>
          </span>
          <div v-if="list.length < 4" class="add">
            <div class="add-field">
              <Icon name="plus" :size="16" />
              <input v-model="q" type="search" :placeholder="list.length ? 'Add another driver' : 'Add a driver to start'" aria-label="Add a driver" role="combobox" :aria-expanded="hits.length > 0" @keydown="pickerKey">
            </div>
            <ul v-if="hits.length" class="hits" role="listbox">
              <li v-for="(h, i) in hits" :key="h.id" role="option" :aria-selected="i === activeHit">
                <button type="button" :class="{ on: i === activeHit }" @click="add(h.id)" @mousemove="activeHit = i"><b>{{ h.name }}</b><span class="muted small">{{ h.sub }}</span></button>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section v-if="!drivers.length">
        <h2 class="section-title">Or start from one of these</h2>
        <div class="suggestions">
          <NuxtLink v-for="sg in SUGGESTIONS" :key="sg.ids" :to="`/compare?drivers=${sg.ids}`" class="card-link suggestion">
            <b>{{ sg.title }}</b>
            <span class="small ink-2">{{ sg.text }}</span>
            <span class="small link-like">Compare <Icon name="right" :size="14" /></span>
          </NuxtLink>
        </div>
      </section>

      <template v-if="drivers.length">
        <div v-if="data?.teammate_pairs.length" class="row wrap">
          <NuxtLink v-for="p in data.teammate_pairs" :key="p.driver_a + p.driver_b" :to="`/teammates/${p.driver_a}/${p.driver_b}`" class="chip">
            Teammates for {{ p.races }} races: {{ nameOf(p.driver_a) }} {{ p.quali_won }}–{{ p.quali_lost }} in qualifying. See the head-to-head
            <Icon name="right" :size="14" />
          </NuxtLink>
        </div>

        <Panel title="Career totals" flush>
          <div class="table-scroll">
            <table class="data">
              <thead>
                <tr>
                  <th />
                  <th v-for="(d, i) in drivers" :key="d.driver.id" class="r"><span class="swatch" :style="{ background: seriesVar(i + 1), marginRight: '6px' }" />{{ d.driver.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in ROWS" :key="row.label">
                  <td class="muted">{{ row.label }}</td>
                  <td v-for="d in drivers" :key="d.driver.id" class="r" :class="{ best: isBest(row, row.get(d.driver)) }">
                    {{ row.get(d.driver) ?? '–' }}{{ row.label.endsWith('rate') && row.get(d.driver) != null ? '%' : '' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Career progression" :note="`Career ${metric} after each race ${axis === 'age' ? 'by age' : 'start'}.`">
          <template #actions>
            <div class="segmented">
              <button v-for="m in METRICS" :key="m.id" :class="{ on: metric === m.id }" @click="metric = m.id">{{ m.label }}</button>
            </div>
            <div class="segmented">
              <button :class="{ on: axis === 'start' }" @click="axis = 'start'">By start</button>
              <button :class="{ on: axis === 'age' }" @click="axis = 'age'">By age</button>
            </div>
          </template>
          <Chart :option="careerChart" :height="400" :compact-height="320" label="Cumulative career totals" share-id="career" />
        </Panel>

        <Panel title="Championship position by season of career">
          <Chart :option="seasonChart" :height="320" label="Championship position in each season of the career" />
        </Panel>
      </template>
    </div>
  </div>
</template>

<style scoped>
.picker {
  gap: 10px;
}
.sel {
  height: 34px;
  padding-right: 4px;
  font-size: 14px;
}
.x {
  border: 0;
  background: none;
  color: var(--muted);
  cursor: pointer;
  display: inline-flex;
  padding: 4px;
  border-radius: 6px;
}
.x:hover {
  background: var(--surface-3);
  color: var(--ink);
}
.add {
  position: relative;
}
.add-field {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px dashed var(--border-strong);
  color: var(--muted);
  width: 260px;
  max-width: 100%;
}
.add-field:focus-within {
  border-style: solid;
  border-color: var(--accent);
}
.add-field input {
  border: 0;
  background: none;
  outline: none;
  flex: 1;
  min-width: 0;
  height: 100%;
  color: var(--ink);
}
.section-title {
  margin-bottom: 12px;
}
.suggestions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(240px, 100%), 1fr));
  gap: 12px;
}
.suggestion {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.link-like {
  color: var(--accent-ink);
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-top: 4px;
}
@media (max-width: 640px) {
  .add,
  .add-field {
    width: 100%;
  }
}
.hits {
  position: absolute;
  z-index: 20;
  top: 42px;
  left: 0;
  width: 320px;
  max-width: 90vw;
  list-style: none;
  margin: 0;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
}
.hits button {
  width: 100%;
  text-align: left;
  border: 0;
  background: none;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}
.hits button.on {
  background: var(--accent-soft);
}
.best {
  font-weight: 700;
  color: var(--ink);
  background: var(--accent-soft);
}
</style>
