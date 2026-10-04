<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { Ref2 } from '~/utils/types'

interface ConstructorDetail {
  constructor: {
    id: string
    name: string
    full_name: string
    country: string | null
    starts: number
    entries: number
    wins: number
    one_twos: number
    podiums: number
    poles: number
    fastest_laps: number
    points: number
    championships: number
    best_championship_position: number | null
  }
  seasons: {
    year: number
    position: number | null
    position_text: string | null
    points: number | null
    starts: number
    wins: number
    podiums: number
    poles: number
    one_twos: number
    drivers: Ref2[] | null
    chassis: Ref2[] | null
    engines: string[] | null
    tyres: string[] | null
  }[]
  lineage: { chain_id: string; step: number; id: string; name: string; year_from: number; year_to: number | null }[]
  retirements: { year: number; category: string; n: number }[]
}

const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error } = await useApi<ConstructorDetail>(() => `/constructors/${id.value}`)
notFoundIf(error, 'Team')
const c = computed(() => data.value?.constructor)
const color = computed(() => teamColor(id.value))

usePageMeta({
  title: () => c.value?.name ?? 'Team',
  description: () => (c.value ? `${c.value.full_name}: ${c.value.wins} wins, ${c.value.poles} poles and ${c.value.championships} constructors' titles. Seasons, drivers, cars and engines.` : undefined),
  eyebrow: () => (c.value ? `Team · ${c.value.country ?? ''}` : undefined),
  stats: () => (c.value ? [['Titles', c.value.championships], ['Wins', c.value.wins], ['Poles', c.value.poles], ['Starts', c.value.starts]] : []),
  color: () => teamColor(id.value),
})

const chains = computed(() => {
  const groups = new Map<string, ConstructorDetail['lineage']>()
  for (const l of data.value?.lineage ?? []) {
    if (!groups.has(l.chain_id)) groups.set(l.chain_id, [])
    groups.get(l.chain_id)!.push(l)
  }
  return [...groups.values()]
})

const seasons = computed(() => data.value?.seasons ?? [])
const positionChart = useChartOption<EChartsOption>(() => ({
  animation: false,
  grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', formatter: (p: unknown) => { const s = seasons.value[(p as { dataIndex: number }[])[0]!.dataIndex]!; return `<b>${s.year}</b><br>${s.position ? `Constructors' championship: ${ordinal(s.position)}` : 'Not classified'}<br>${s.wins} wins · ${s.podiums} podiums` } },
  xAxis: { type: 'category', data: seasons.value.map((s) => String(s.year)) },
  yAxis: { type: 'value', inverse: true, min: 1, minInterval: 1, axisLabel: { formatter: (v: number) => ordinal(v) } },
  series: [{ type: 'line', data: seasons.value.map((s) => s.position), color: color.value, symbolSize: 8, connectNulls: false, itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 } }],
}))
const winsChart = useChartOption<EChartsOption>(() => ({
  animation: false,
  legend: { top: 0, left: 0 },
  grid: { left: 8, right: 8, top: 32, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: seasons.value.map((s) => String(s.year)) },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    { name: 'Wins', type: 'bar', data: seasons.value.map((s) => s.wins), color: seriesColor(1), barMaxWidth: 16 },
    { name: 'Poles', type: 'bar', data: seasons.value.map((s) => s.poles), color: seriesColor(2), barMaxWidth: 16 },
  ],
}))
interface CarSeason {
  year: number
  gap_pct: number
  raw_gap_pct: number
  rank: number
  cars: number
  races: number
  chassis: { id: string; name: string }[]
}
const { data: carPace } = useFetch<{ seasons: CarSeason[] }>(() => `/api/car-ratings/team/${id.value}`, { server: false, key: `car-pace:${id.value}` })
const carSeasons = computed(() => carPace.value?.seasons ?? [])
const carChart = useChartOption<EChartsOption>(() => {
  const rows = carSeasons.value
  const all = seasons.value.map((s) => s.year)
  const byYear = new Map(rows.map((r) => [r.year, r]))
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (p: unknown) => {
        const r = byYear.get(all[(p as { dataIndex: number }[])[0]!.dataIndex]!)
        if (!r) return 'No qualifying times'
        const car = r.chassis.map((c) => c.name).join(' / ')
        return `<b>${r.year}</b>${car ? ` · ${car}` : ''}<br>${r.rank === 1 ? 'Fastest car' : `+${r.gap_pct.toFixed(2)}% to the fastest car`}<br>${ordinal(r.rank)} of ${r.cars} cars`
      },
    },
    xAxis: { type: 'category', data: all.map(String) },
    yAxis: { type: 'value', inverse: true, min: 0, axisLabel: { formatter: (v: number) => (v === 0 ? 'Fastest' : `+${v}%`) } },
    series: [
      {
        type: 'line',
        data: all.map((y) => byYear.get(y)?.gap_pct ?? null),
        color: color.value,
        symbolSize: 7,
        connectNulls: false,
        itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 },
      },
    ],
  }
})
const fastestSeasons = computed(() => carSeasons.value.filter((r) => r.rank === 1).map((r) => r.year))

const CATS = [
  { id: 'technical', label: 'Technical failure' },
  { id: 'accident', label: 'Crash or collision' },
  { id: 'rules', label: 'Penalty or rules' },
  { id: 'other', label: 'Other' },
]
const retireChart = useChartOption<EChartsOption>(() => {
  const yrs = seasons.value.map((s) => s.year)
  const get = (y: number, cat: string) => data.value?.retirements.find((r) => r.year === y && r.category === cat)?.n ?? 0
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 8, top: 32, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: yrs.map(String) },
    yAxis: { type: 'value', minInterval: 1 },
    series: CATS.map((cat, i) => ({
      name: cat.label,
      type: 'bar',
      stack: 'r',
      barMaxWidth: 18,
      color: seriesColor(i + 1),
      itemStyle: { borderColor: cssVar('--surface'), borderWidth: 1, borderRadius: 0 },
      data: yrs.map((y) => get(y, cat.id) || null),
    })),
  }
})
</script>

<template>
  <div v-if="data && c">
    <PageHeader :title="c.name" :crumbs="[{ to: '/constructors', label: 'Teams' }, { label: c.country ?? '' }]">
      <template #sub>{{ c.full_name }}. Raced {{ years(seasons[0]?.year, seasons.at(-1)?.year) }}.</template>
    </PageHeader>

    <div class="stack">
      <Tiles>
        <StatTile label="Constructors' titles" :value="c.championships" :hint="c.best_championship_position ? `Best: ${ordinal(c.best_championship_position)}` : ''" />
        <StatTile label="Wins" :value="c.wins" :hint="c.starts ? `${((c.wins / c.starts) * 100).toFixed(1)}% of starts` : ''" />
        <StatTile label="One-two finishes" :value="c.one_twos" />
        <StatTile label="Podiums" :value="c.podiums" />
        <StatTile label="Poles" :value="c.poles" />
        <StatTile label="Starts" :value="c.starts" />
        <StatTile label="Points" :value="points(c.points)" />
      </Tiles>

      <Panel v-if="chains.length" title="Lineage" note="The same team under different names and owners.">
        <div v-for="(chain, i) in chains" :key="i" class="chain">
          <template v-for="(l, j) in chain" :key="l.step">
            <NuxtLink :to="`/constructors/${l.id}`" class="chip" :class="{ on: l.id === id }">
              <span class="swatch" :style="{ background: teamColor(l.id) }" /> {{ l.name }} <span class="muted">{{ years(l.year_from, l.year_to ?? undefined) }}{{ l.year_to ? '' : '–' }}</span>
            </NuxtLink>
            <Icon v-if="j < chain.length - 1" name="right" :size="14" class="muted" />
          </template>
        </div>
      </Panel>

      <div class="grid-12">
        <Panel class="span-6" title="Constructors' championship position">
          <Chart :option="positionChart" :height="260" label="Championship position by season" share-id="team-position" />
        </Panel>
        <Panel class="span-6" title="Wins and poles per season">
          <Chart :option="winsChart" :height="260" label="Wins and poles by season" />
        </Panel>
      </div>

      <Panel
        v-if="carSeasons.length"
        title="How fast the car was"
        :note="`Qualifying pace with the drivers taken out, as a gap to the fastest car of each season.${fastestSeasons.length > 6 ? ` Fastest car in ${fastestSeasons.length} seasons, most recently ${fastestSeasons.at(-1)}.` : fastestSeasons.length ? ` Fastest car in ${listing(fastestSeasons.map(String))}.` : ''}`"
      >
        <template #actions><NuxtLink class="btn ghost" to="/ratings?kind=cars">All cars</NuxtLink></template>
        <Chart :option="carChart" :height="260" label="Gap to the fastest car by season" share-id="car-pace" />
      </Panel>

      <Panel title="Reliability" note="Retirements per season, by cause.">
        <Chart :option="retireChart" :height="260" label="Retirements by cause and season" share-id="reliability" />
      </Panel>

      <Panel title="Seasons" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr><th>Year</th><th class="c">Pos</th><th class="r hide-sm">Points</th><th class="r">Wins</th><th class="r hide-md">Podiums</th><th>Drivers</th><th class="hide-sm">Car</th><th class="hide-md">Engine</th><th class="hide-md">Tyres</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in seasons.slice().reverse()" :key="s.year">
                <td><NuxtLink class="link" :to="`/seasons/${s.year}`"><b>{{ s.year }}</b></NuxtLink></td>
                <td class="c"><ResultPos :position="s.position" :text="s.position_text ?? '–'" /></td>
                <td class="r hide-sm">{{ points(s.points) }}</td>
                <td class="r"><b v-if="s.wins">{{ s.wins }}</b></td>
                <td class="r hide-md">{{ s.podiums || '' }}</td>
                <td class="small">
                  <template v-for="(dr, i) in s.drivers ?? []" :key="dr.id"><NuxtLink class="link" :to="`/drivers/${dr.id}`">{{ dr.name }}</NuxtLink><template v-if="i < (s.drivers?.length ?? 0) - 1">, </template></template>
                </td>
                <td class="small nowrap hide-sm"><template v-for="(ch, i) in s.chassis ?? []" :key="ch.id"><NuxtLink class="link" :to="`/cars/${ch.id}`">{{ ch.name }}</NuxtLink><template v-if="i < (s.chassis?.length ?? 0) - 1">, </template></template></td>
                <td class="small hide-md">{{ (s.engines ?? []).join(', ') }}</td>
                <td class="small muted hide-md">{{ (s.tyres ?? []).join(', ') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.chain {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.chain .chip.on {
  border-color: var(--accent);
  background: var(--accent-soft);
}
</style>
