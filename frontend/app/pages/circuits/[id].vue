<script setup lang="ts">
import type { EChartsOption } from 'echarts'

interface CircuitDetail {
  circuit: {
    id: string
    name: string
    full_name: string
    previous_names: string | null
    type: string
    direction: string | null
    place_name: string
    country: string
    latitude: number
    longitude: number
    length: number | null
    turns: number | null
    races: number
  }
  layouts: { id: string; length: number | null; turns: number | null; path: string | null; first_year: number | null; last_year: number | null; races: number }[]
  races: {
    year: number
    round: number
    grand_prix: string
    layout_id: string
    laps: number | null
    winner_id: string | null
    winner: string | null
    winner_constructor_id: string | null
    winner_constructor: string | null
    winner_grid: number | null
    pole_id: string | null
    pole: string | null
    fastest_lap_id: string | null
    fastest_lap_driver: string | null
    fastest_lap_time: string | null
    fastest_lap_ms: number | null
  }[]
  stats: { races: number; won_from_pole: number; won_from_outside_top3: number; different_winners: number }
  most_wins: { drivers: { id: string; name: string; wins: number }[]; constructors: { id: string; name: string; wins: number }[] }
}

const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error } = await useApi<CircuitDetail>(() => `/circuits/${id.value}`)
notFoundIf(error, 'Circuit')
const c = computed(() => data.value?.circuit)
const usedLayouts = computed(() => (data.value?.layouts ?? []).filter((l) => l.races > 0 && l.path))
const layoutId = useQueryState('layout', '')
const layout = computed(() => usedLayouts.value.find((l) => l.id === layoutId.value) ?? usedLayouts.value.at(-1))

usePageMeta({
  title: () => c.value?.name ?? 'Circuit',
  description: () => (c.value ? `${c.value.full_name}, ${c.value.place_name}: ${c.value.races} Formula 1 races, winners, layouts and lap records.` : undefined),
  eyebrow: () => (c.value ? `Circuit · ${c.value.place_name}, ${c.value.country}` : undefined),
  stats: () => (data.value ? [['Races', data.value.stats.races], ['Won from pole', data.value.stats.races ? `${Math.round((data.value.stats.won_from_pole / data.value.stats.races) * 100)}%` : null], ['Most wins', data.value.most_wins.drivers[0]?.name], ['Length', c.value?.length ? `${c.value.length} km` : null]] : []),
})

const finished = computed(() => (data.value?.races ?? []).filter((r) => r.winner_id))
const gridChart = useChartOption<EChartsOption>(() => {
  const counts = new Map<number, number>()
  for (const r of finished.value) if (r.winner_grid) counts.set(r.winner_grid, (counts.get(r.winner_grid) ?? 0) + 1)
  const max = Math.max(1, ...counts.keys())
  const cats = Array.from({ length: max }, (_, i) => i + 1)
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: 'item', formatter: (p: unknown) => { const t = p as { name: string; value: number }; return `Won from <b>P${t.name}</b>: ${t.value} time${t.value === 1 ? '' : 's'}` } },
    xAxis: { type: 'category', data: cats.map(String), name: 'Grid', axisLabel: { formatter: (v: string) => `P${v}` } },
    yAxis: { type: 'value', minInterval: 1, name: 'Wins' },
    series: [{ type: 'bar', data: cats.map((g) => counts.get(g) ?? 0), color: seriesColor(1), barMaxWidth: 22 }],
  }
})
const lapChart = useChartOption<EChartsOption>(() => {
  const lid = layout.value?.id
  const rows = finished.value.filter((r) => r.layout_id === lid && r.fastest_lap_ms).slice().reverse()
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis', formatter: (p: unknown) => { const r = rows[(p as { dataIndex: number }[])[0]!.dataIndex]!; return `<b>${r.year}</b><br>${r.fastest_lap_time} · ${r.fastest_lap_driver}` } },
    xAxis: { type: 'category', data: rows.map((r) => String(r.year)) },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => lapTime(v) } },
    series: [{ type: 'line', data: rows.map((r) => r.fastest_lap_ms), color: seriesColor(1), symbolSize: 8, itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 } }],
  }
})
const TYPES: Record<string, string> = { RACE: 'Race circuit', STREET: 'Street circuit', ROAD: 'Road course' }
</script>

<template>
  <div v-if="data && c">
    <PageHeader :title="c.name" :crumbs="[{ to: '/circuits', label: 'Circuits' }, { label: `${TYPES[c.type] ?? c.type} · ${c.place_name}, ${c.country}` }]">
      <template #sub>
        {{ c.full_name }}<template v-if="c.length">, {{ num(c.length, 3) }} km, {{ c.turns }} turns</template><template v-if="c.direction">, run {{ c.direction.toLowerCase().replace('_', ' ') }}</template>.
        <template v-if="c.previous_names"> Previously {{ c.previous_names }}.</template>
      </template>
    </PageHeader>

    <div class="stack">
      <div class="grid-12">
        <Panel class="span-4" title="Layout" :note="layout ? `${years(layout.first_year, layout.last_year)} · ${layout.races} races${layout.length ? ` · ${num(layout.length, 3)} km` : ''}` : ''">
          <svg v-if="layout?.path" viewBox="0 0 500 500" class="layout" role="img" :aria-label="`${c.name} layout`"><path :d="layout.path" /></svg>
          <div v-if="usedLayouts.length > 1" class="row wrap">
            <button v-for="l in usedLayouts" :key="l.id" class="chip" :class="{ on: l.id === layout?.id }" :aria-pressed="l.id === layout?.id" @click="layoutId = l.id">
              {{ years(l.first_year, l.last_year) }}
            </button>
          </div>
        </Panel>
        <div class="span-8 stack">
          <Tiles>
            <StatTile label="Races held" :value="data.stats.races" />
            <StatTile label="Won from pole" :value="data.stats.races ? `${Math.round((data.stats.won_from_pole / data.stats.races) * 100)}%` : '–'" :hint="`${data.stats.won_from_pole} of ${data.stats.races}`" />
            <StatTile label="Won from outside the top 3" :value="data.stats.won_from_outside_top3" />
            <StatTile label="Different winners" :value="data.stats.different_winners" />
          </Tiles>
          <div class="grid-12">
            <Panel class="span-6" title="Most wins">
              <ol class="board">
                <li v-for="d in data.most_wins.drivers" :key="d.id"><NuxtLink :to="`/drivers/${d.id}`">{{ d.name }}</NuxtLink><b>{{ d.wins }}</b></li>
              </ol>
            </Panel>
            <Panel class="span-6" title="Most wins by team">
              <ol class="board">
                <li v-for="t in data.most_wins.constructors" :key="t.id"><TeamName :id="t.id" :name="t.name" /><b>{{ t.wins }}</b></li>
              </ol>
            </Panel>
          </div>
        </div>
      </div>

      <div class="grid-12">
        <Panel class="span-6" title="Where winners started" note="Grid position of every winner here.">
          <Chart :option="gridChart" :height="240" label="Count of wins by starting position" />
        </Panel>
        <Panel class="span-6" title="Fastest race lap" note="Per year, on the layout shown above.">
          <Chart :option="lapChart" :height="240" label="Fastest race lap by year" />
        </Panel>
      </div>

      <CircuitConditions :circuit-id="c.id" />

      <Panel title="Races" flush>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th>Year</th><th>Winner</th><th class="hide-sm">Team</th><th class="r">From</th><th class="hide-md">Pole</th><th class="hide-md">Fastest lap</th></tr></thead>
            <tbody>
              <tr v-for="r in data.races" :key="`${r.year}-${r.round}`">
                <td class="nowrap"><NuxtLink class="link" :to="`/races/${r.year}/${r.round}`"><b>{{ r.year }}</b></NuxtLink> <span class="tiny muted hide-sm">{{ r.grand_prix }}</span></td>
                <td>
                  <NuxtLink v-if="r.winner_id" :to="`/drivers/${r.winner_id}`">{{ r.winner }}</NuxtLink><span v-else class="muted small">Upcoming</span>
                  <span v-if="r.winner_constructor" class="sub-line only-sm">{{ r.winner_constructor }}</span>
                </td>
                <td class="hide-sm"><TeamName v-if="r.winner_constructor_id" :id="r.winner_constructor_id" :name="r.winner_constructor!" /></td>
                <td class="r">{{ r.winner_grid ? `P${r.winner_grid}` : '' }}</td>
                <td class="small hide-md"><NuxtLink v-if="r.pole_id" :to="`/drivers/${r.pole_id}`">{{ r.pole }}</NuxtLink></td>
                <td class="small nowrap hide-md">{{ r.fastest_lap_time ?? '' }} <span class="muted">{{ r.fastest_lap_driver ?? '' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.layout {
  width: 100%;
  max-width: 320px;
  aspect-ratio: 1;
  margin: 0 auto;
  display: block;
}
.layout path {
  fill: none;
  stroke: var(--ink);
  stroke-width: 10;
  stroke-linejoin: round;
}
.board {
  list-style: none;
  margin: 0;
  padding: 0;
}
.board li {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  border-bottom: 1px solid var(--grid);
}
.board li:last-child {
  border-bottom: 0;
}
</style>
