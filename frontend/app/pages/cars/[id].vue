<script setup lang="ts">
import type { EChartsOption } from 'echarts'

interface Car {
  car: { id: string; name: string; full_name: string; constructor_id: string; constructor: string }
  years: number[]
  entrants: string[]
  era: { name: string; engine: string; summary: string; from: number; to: number | null } | null
  engines: { id: string; full_name: string; capacity: number | null; configuration: string | null; aspiration: string | null; manufacturer: string }[]
  drivers: { id: string; name: string; year: number }[]
  results: { races: number; wins: number; podiums: number; poles: number; points: number; retirements: number; starts: number }
  standings: { year: number; position: number | null; points: number }[]
  qualifying_pace: { year: number; round: number; abbreviation: string; gap_pct: number }[]
  average_gap_pct: number | null
  shared_seasons: { year: number; id: string; name: string }[]
}

const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error } = await useApi<Car>(() => `/cars/${id.value}`)
notFoundIf(error, 'Car')
const c = computed(() => data.value?.car)

usePageMeta({
  title: () => c.value?.full_name ?? 'Car',
  description: () => (data.value && c.value ? `${c.value.full_name} (${data.value.years.join(', ')}): ${data.value.results.wins} wins, ${data.value.results.poles} poles, engines, drivers and qualifying pace.` : undefined),
  eyebrow: () => (c.value ? `Car · ${c.value.constructor}` : undefined),
  stats: () => (data.value ? [['Wins', data.value.results.wins], ['Poles', data.value.results.poles], ['Podiums', data.value.results.podiums], ['Seasons', data.value.years.join(', ')]] : []),
  color: () => (c.value ? teamColor(c.value.constructor_id) : undefined),
})

const ASPIRATION: Record<string, string> = {
  NATURALLY_ASPIRATED: 'naturally aspirated',
  TURBOCHARGED: 'turbocharged',
  SUPERCHARGED: 'supercharged',
  TURBOCHARGED_HYBRID: 'turbo hybrid',
}
const paceChart = useChartOption<EChartsOption>(() => {
  const p = data.value?.qualifying_pace ?? []
  const color = teamColor(c.value?.constructor_id)
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
    tooltip: { trigger: 'axis', formatter: (x: unknown) => { const r = p[(x as { dataIndex: number }[])[0]!.dataIndex]!; return `<b>${r.year} ${r.abbreviation}</b><br>${r.gap_pct === 0 ? 'Fastest car' : `+${r.gap_pct.toFixed(2)}% to the fastest car`}` } },
    xAxis: { type: 'category', data: p.map((r) => `${data.value!.years.length > 1 ? `${r.year} ` : ''}${r.abbreviation}`) },
    yAxis: { type: 'value', inverse: true, min: 0, axisLabel: { formatter: (v: number) => (v === 0 ? 'Fastest' : `+${v}%`) } },
    series: [
      {
        type: 'line',
        data: p.map((r) => r.gap_pct),
        color,
        symbolSize: 9,
        lineStyle: { width: 2 },
        itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 },
      },
    ],
  }
})
const driverNames = computed(() => {
  const m = new Map<string, string>()
  for (const d of data.value?.drivers ?? []) m.set(d.id, d.name)
  return [...m.entries()]
})
</script>

<template>
  <div v-if="data && c">
    <PageHeader :title="c.full_name" :crumbs="[{ to: '/constructors', label: 'Teams' }, { to: `/constructors/${c.constructor_id}`, label: c.constructor }, { label: data.years.join(', ') }]">
      <template #sub>
        Raced by {{ data.entrants.join(', ') }} in {{ listing(data.years.map(String)) }}<template v-if="data.era">, in the <NuxtLink class="link" to="/eras">{{ data.era.name.toLowerCase() }} era</NuxtLink></template>.
      </template>
    </PageHeader>
    <div class="stack">
      <Tiles>
        <StatTile label="Wins" :value="data.results.wins" :hint="`${data.results.races} races`" />
        <StatTile label="Poles" :value="data.results.poles" />
        <StatTile label="Podiums" :value="data.results.podiums" />
        <StatTile label="Points" :value="points(data.results.points)" />
        <StatTile label="Finish rate" :value="data.results.starts ? `${Math.round((1 - data.results.retirements / data.results.starts) * 100)}%` : '–'" :hint="`${data.results.retirements} retirements`" />
        <StatTile label="Qualifying pace" :value="data.average_gap_pct == null ? '–' : data.average_gap_pct === 0 ? 'Fastest' : `+${data.average_gap_pct.toFixed(2)}%`" hint="Median gap to the fastest car" />
      </Tiles>
      <div class="grid-12">
        <Panel class="span-8" title="Qualifying pace, race by race" note="The team's best qualifying lap as a percentage slower than the fastest car.">
          <Chart :option="paceChart" :height="280" :compact-height="240" label="Qualifying gap to the fastest car per race" share-id="car-pace" />
        </Panel>
        <Panel class="span-4" title="The car">
          <dl class="facts">
            <dt>Team</dt><dd><TeamName :id="c.constructor_id" :name="c.constructor" /></dd>
            <dt>Engine</dt>
            <dd>
              <div v-for="e in data.engines" :key="e.id">
                <b>{{ e.full_name }}</b>
                <div class="small muted">{{ [e.capacity ? `${e.capacity} litre` : null, e.configuration, e.aspiration ? ASPIRATION[e.aspiration] ?? e.aspiration.toLowerCase() : null].filter(Boolean).join(', ') }}</div>
              </div>
            </dd>
            <dt>Drivers</dt>
            <dd><template v-for="([did, name], i) in driverNames" :key="did"><NuxtLink class="link" :to="`/drivers/${did}`">{{ name }}</NuxtLink><template v-if="i < driverNames.length - 1">, </template></template></dd>
            <template v-if="data.standings.length">
              <dt>Championship</dt>
              <dd><span v-for="s in data.standings" :key="s.year" class="block">{{ s.year }}: {{ s.position ? ordinal(s.position) : 'not classified' }}, {{ points(s.points) }} points</span></dd>
            </template>
            <template v-if="data.era">
              <dt>Rules</dt>
              <dd class="small ink-2">{{ data.era.engine }}. {{ data.era.summary }}</dd>
            </template>
          </dl>
        </Panel>
      </div>
      <p v-if="data.shared_seasons.length" class="small muted">
        The team also raced
        <template v-for="(o, i) in data.shared_seasons" :key="o.id + o.year"><NuxtLink class="link" :to="`/cars/${o.id}`">{{ o.name }}</NuxtLink> ({{ o.year }}){{ i < data.shared_seasons.length - 1 ? ', ' : '' }}</template>
        in the same {{ data.years.length > 1 ? 'seasons' : 'season' }}, so race results above are for the team as a whole.
      </p>
    </div>
  </div>
</template>

<style scoped>
.facts {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 16px;
  margin: 0;
}
.facts dt {
  color: var(--muted);
  font-size: 13px;
}
.facts dd {
  margin: 0;
}
.block {
  display: block;
}
</style>
