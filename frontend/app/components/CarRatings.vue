<script setup lang="ts">
// Car performance from qualifying pace with the drivers taken out (backend/paddock/cars.py).
import type { EChartsOption } from 'echarts'

interface Car {
  year: number
  constructor_id: string
  constructor: string
  entrant: string | null
  gap_pct: number
  raw_gap_pct: number
  races: number
  rank: number
  cars: number
  margin_pct: number | null
  percentile: number
  chassis: { id: string; name: string }[]
}
interface Team {
  rank: number
  constructor_id: string
  constructor: string
  seasons: number
  first_year: number
  last_year: number
  fastest_car_seasons: number
  top3_seasons: number
  average_percentile: number
  median_gap_pct: number
}

const { data } = await useApi<{ dominant: Car[]; fastest: Car[]; constructors: Team[]; method: string }>('/car-ratings?limit=15')
const yearsList = computed(() => (data.value?.fastest ?? []).map((c) => c.year).reverse())
const year = useQueryState('year', '')
const picked = computed(() => year.value || String(yearsList.value[0] ?? ''))
const { data: season } = useFetch<{ cars: Car[] }>(() => `/api/car-ratings/${picked.value}`, { server: false, key: 'car-season' })

const carName = (c: Car) => (c.chassis.length ? c.chassis.map((x) => x.name).join(' / ') : c.constructor)
const maxMargin = computed(() => Math.max(0.1, ...(data.value?.dominant ?? []).map((c) => c.margin_pct ?? 0)))

const fastestChart = useChartOption<EChartsOption>(() => {
  const rows = data.value?.fastest ?? []
  return {
    animation: false,
    grid: { left: 8, right: 12, top: 16, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p: unknown) => {
        const c = rows[(p as { dataIndex: number }[])[0]!.dataIndex]!
        return `<b>${c.year}</b> · ${carName(c)}<br>${c.constructor}<br>${c.margin_pct != null ? `${c.margin_pct.toFixed(2)}% faster than the next car` : 'Only car with times'}`
      },
    },
    xAxis: { type: 'category', data: rows.map((c) => String(c.year)) },
    yAxis: { type: 'value', name: 'Lead over the next car', nameTextStyle: { align: 'left' }, axisLabel: { formatter: (v: number) => `${v}%` } },
    series: [
      {
        type: 'bar',
        barMaxWidth: 12,
        data: rows.map((c) => ({ value: c.margin_pct ?? 0, itemStyle: { color: teamColor(c.constructor_id), borderRadius: [3, 3, 0, 0] } })),
      },
    ],
  }
})

const seasonChart = useChartOption<EChartsOption>(() => {
  const rows = (season.value?.cars ?? []).slice().reverse()
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 24, top: 32, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p: unknown) => {
        const c = rows[(p as { dataIndex: number }[])[0]!.dataIndex]!
        return `<b>${esc(c.constructor)}</b> · ${esc(carName(c))}<br>Drivers taken out: ${c.gap_pct === 0 ? 'fastest car' : `+${c.gap_pct.toFixed(2)}%`}<br>Team's best lap: ${c.raw_gap_pct === 0 ? 'pole' : `+${c.raw_gap_pct.toFixed(2)}%`} (median, ${c.races} races)`
      },
    },
    xAxis: { type: 'value', axisLabel: { formatter: (v: number) => (v === 0 ? '0' : `+${v}%`) } },
    yAxis: { type: 'category', data: rows.map((c) => c.constructor), axisLabel: { fontWeight: 600 } },
    series: [
      { name: 'Car, drivers taken out', type: 'bar', data: rows.map((c) => c.gap_pct), color: seriesColor(1), barMaxWidth: 10, itemStyle: { borderRadius: [0, 3, 3, 0] } },
      { name: "Team's best lap, gap to pole", type: 'bar', data: rows.map((c) => c.raw_gap_pct), color: seriesColor(2), barMaxWidth: 10, itemStyle: { borderRadius: [0, 3, 3, 0] } },
    ],
  }
})
function esc(s: string) {
  return s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]!)
}
</script>

<template>
  <div v-if="data" class="stack">
    <Panel title="The fastest car of every season" note="How far ahead of the next car the fastest car was in qualifying, with the drivers taken out. Hover for the car.">
      <Chart :option="fastestChart" :height="280" :compact-height="240" label="Lead of the fastest car over the next car, by season" share-id="fastest-cars" />
    </Panel>

    <div class="grid-12">
      <Panel class="span-6" title="Most dominant cars" note="Biggest lead over the next car in the same season." flush>
        <ol class="board">
          <li v-for="(c, i) in data.dominant" :key="`${c.year}-${c.constructor_id}`">
            <span class="rank num">{{ i + 1 }}</span>
            <div class="who">
              <b>
                <template v-for="(ch, j) in c.chassis" :key="ch.id"><NuxtLink :to="`/cars/${ch.id}`">{{ ch.name }}</NuxtLink><template v-if="j < c.chassis.length - 1"> / </template></template>
                <template v-if="!c.chassis.length">{{ c.constructor }}</template>
              </b>
              <span class="sub-line"><NuxtLink class="link" :to="`/seasons/${c.year}`">{{ c.year }}</NuxtLink> · <TeamName :id="c.constructor_id" :name="c.constructor" /></span>
            </div>
            <div class="bar" role="img" :aria-label="`${c.margin_pct}% ahead`"><span :style="{ width: `${((c.margin_pct ?? 0) / maxMargin) * 100}%` }" /></div>
            <span class="value num">{{ c.margin_pct?.toFixed(2) }}%</span>
          </li>
        </ol>
      </Panel>
      <Panel class="span-6" title="Teams by how fast their cars were" :note="`Average place of their car in each season's order, as a share of the field (100% = always fastest). Teams with five seasons or more.`" flush>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th class="r">#</th><th>Team</th><th class="r">Fastest car</th><th class="r hide-sm">Top three</th><th class="r">Average</th></tr></thead>
            <tbody>
              <tr v-for="t in data.constructors.slice(0, 15)" :key="t.constructor_id">
                <td class="r muted">{{ t.rank }}</td>
                <td><TeamName :id="t.constructor_id" :name="t.constructor" /><span class="sub-line">{{ years(t.first_year, t.last_year) }} · {{ t.seasons }} seasons</span></td>
                <td class="r num">{{ t.fastest_car_seasons || '' }}</td>
                <td class="r num hide-sm">{{ t.top3_seasons || '' }}</td>
                <td class="r num"><b>{{ Math.round(t.average_percentile * 100) }}%</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>

    <Panel title="One season" note="Each team's car as a gap to the fastest car, with the drivers taken out, next to the plain gap from the team's best qualifying laps.">
      <template #actions>
        <UiSelect :model-value="picked" label="Season" :options="yearsList.map((y) => ({ value: String(y), label: String(y) }))" searchable @update:model-value="(v: string) => (year = v)" />
      </template>
      <Chart v-if="season" :option="seasonChart" :height="Math.max(260, season.cars.length * 30 + 60)" :label="`Car pace in ${picked}`" share-id="car-season" />
      <div v-else class="skeleton" style="height: 320px" />
    </Panel>

    <Panel title="How it works">
      <div class="prose small">
        <p>Every qualifying lap is a gap to pole. A fit splits each gap into a part for the car (one number per team per season) and a part for the driver (one number per career), so a great driver does not flatter their car and a weak one does not sink it. Drivers who moved between teams tie all the cars together.</p>
        <p><b>Limits.</b> Qualifying is one lap on low fuel; race pace can tell a different story. A driver's form is taken as the same across a whole career. Laps more than 7% off pole are left out as failed attempts, which also hides some very slow cars. Privateers running a customer car count as their own entry.</p>
        <p class="muted">The code is open: <code>backend/paddock/cars.py</code>.</p>
      </div>
    </Panel>
  </div>
</template>

<style scoped>
.board {
  list-style: none;
  margin: 0;
  padding: 0 0 8px;
}
.board li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1.4fr) minmax(0, 1fr) 56px;
  gap: 12px;
  align-items: center;
  padding: 8px var(--pad);
  border-bottom: 1px solid var(--grid);
}
.board li:last-child {
  border-bottom: 0;
}
.rank {
  color: var(--muted);
  text-align: right;
  font-weight: 600;
}
.who {
  min-width: 0;
}
.bar {
  height: 8px;
  border-radius: 4px;
  background: var(--surface-2);
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: var(--series-1);
}
.value {
  text-align: right;
  font-weight: 650;
}
.prose p + p {
  margin-top: 10px;
}
@media (max-width: 640px) {
  .board li {
    grid-template-columns: 24px minmax(0, 1fr) 52px;
  }
  .bar {
    display: none;
  }
}
</style>
