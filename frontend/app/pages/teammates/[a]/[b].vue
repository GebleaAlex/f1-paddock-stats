<script setup lang="ts">
import type { EChartsOption } from 'echarts'

interface Summary {
  races: number
  first_year: number
  last_year: number
  quali_won: number
  quali_lost: number
  race_won: number
  race_lost: number
  points_me: number
  points_mate: number
  median_gap_pct: number | null
  gap_races: number
}
interface H2H {
  driver: { id: string; name: string; abbreviation: string }
  mate: { id: string; name: string; abbreviation: string }
  summary: Summary
  seasons: (Summary & { year: number })[]
  races: {
    race_id: number
    year: number
    round: number
    grand_prix: string
    abbreviation: string
    constructor: string
    constructor_id: string
    quali_me: number | null
    quali_mate: number | null
    race_me: number | null
    race_mate: number | null
    race_text_me: string
    race_text_mate: string
    points_me: number
    points_mate: number
    reason_me: string | null
    reason_mate: string | null
    gap_pct: number | null
  }[]
}

const route = useRoute()
const a = computed(() => String(route.params.a))
const b = computed(() => String(route.params.b))
const { data, error } = await useApi<H2H>(() => `/teammates/${a.value}/${b.value}`)
notFoundIf(error, 'Pairing')

const me = computed(() => data.value?.driver)
const mate = computed(() => data.value?.mate)
const s = computed(() => data.value?.summary)
usePageMeta({
  title: () => (me.value && mate.value ? `${me.value.name} vs ${mate.value.name}` : 'Head-to-head'),
  description: () =>
    s.value && me.value && mate.value
      ? `${me.value.name} against ${mate.value.name} as teammates: qualifying ${s.value.quali_won}-${s.value.quali_lost}, races ${s.value.race_won}-${s.value.race_lost}, ${s.value.races} races together.`
      : undefined,
  eyebrow: 'Teammate head-to-head',
  stats: () => (s.value ? [['Qualifying', `${s.value.quali_won}–${s.value.quali_lost}`], ['Races', `${s.value.race_won}–${s.value.race_lost}`], ['Points', `${points(s.value.points_me)}–${points(s.value.points_mate)}`], ['Together', `${s.value.races} races`]] : []),
})

// Template colours use CSS variables so server and browser render the same markup in either theme.
const colorMe = seriesVar(1)
const colorMate = seriesVar(2)

const gapChart = useChartOption<EChartsOption>(() => {
  const races = (data.value?.races ?? []).filter((r) => r.gap_pct != null && Math.abs(r.gap_pct) < 5)
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 24, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const r = races[(p as { dataIndex: number }).dataIndex]!
        const faster = r.gap_pct! < 0 ? me.value!.name : mate.value!.name
        return `<b>${r.year} ${r.grand_prix}</b><br>${faster} faster by ${Math.abs(r.gap_pct!).toFixed(3)}%<br>Qualified P${r.quali_me ?? '–'} vs P${r.quali_mate ?? '–'}`
      },
    },
    xAxis: { type: 'category', data: races.map((r) => `${r.year} ${r.abbreviation}`), axisLabel: { interval: 'auto', fontSize: 10 } },
    yAxis: {
      type: 'value',
      name: `← ${me.value?.abbreviation ?? ''} faster · ${mate.value?.abbreviation ?? ''} faster →`,
      nameLocation: 'middle',
      nameGap: 44,
      axisLabel: { formatter: (v: number) => `${v > 0 ? '+' : ''}${v}%` },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 12,
        data: races.map((r) => ({
          value: r.gap_pct,
          itemStyle: { color: r.gap_pct! < 0 ? seriesColor(1) : seriesColor(2), borderRadius: r.gap_pct! < 0 ? [0, 0, 4, 4] : [4, 4, 0, 0] },
        })),
      },
    ],
  }
})

const runningChart = useChartOption<EChartsOption>(() => {
  const races = data.value?.races ?? []
  let q = 0
  let r = 0
  const quali: number[] = []
  const race: number[] = []
  for (const x of races) {
    if (x.quali_me != null && x.quali_mate != null) q += x.quali_me < x.quali_mate ? 1 : -1
    if (x.race_me != null && x.race_mate != null) r += x.race_me < x.race_mate ? 1 : -1
    quali.push(q)
    race.push(r)
  }
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 16, top: 36, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: races.map((x) => `${x.year} ${x.abbreviation}`), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: 'Qualifying duels', type: 'line', step: 'end', data: quali, color: seriesColor(1), showSymbol: false },
      { name: 'Race duels', type: 'line', step: 'end', data: race, color: seriesColor(3), showSymbol: false },
    ],
  }
})

function outcome(pos: number | null, text: string) {
  return pos ? `P${pos}` : text === 'DNF' ? 'Ret' : text
}
</script>

<template>
  <div v-if="data && me && mate && s">
    <PageHeader :title="`${me.name} vs ${mate.name}`" :crumbs="[{ to: '/teammates', label: 'Teammates' }, { label: `${listing([...new Set(data.races.map((r) => r.constructor))])} · ${years(s.first_year, s.last_year)}` }]">
      <template #sub>{{ s.races }} races as teammates.</template>
      <NuxtLink class="btn" :to="`/teammates/${mate.id}/${me.id}`"><Icon name="swap" :size="16" /> Swap sides</NuxtLink>
      <NuxtLink class="btn" :to="`/compare?drivers=${me.id},${mate.id}`">Compare careers</NuxtLink>
    </PageHeader>

    <div class="stack">
      <div class="versus panel">
        <div class="side">
          <span class="swatch" :style="{ background: colorMe }" />
          <NuxtLink :to="`/drivers/${me.id}`"><b>{{ me.name }}</b></NuxtLink>
        </div>
        <div class="rows">
          <div v-for="row in [
            { label: 'Qualifying', a: s.quali_won, b: s.quali_lost },
            { label: 'Race (both finished)', a: s.race_won, b: s.race_lost },
            { label: 'Points', a: s.points_me, b: s.points_mate },
          ]" :key="row.label" class="vs-row">
            <b class="num left">{{ points(row.a) }}</b>
            <div class="vs-bar">
              <span :style="{ width: `${row.a + row.b ? (row.a / (row.a + row.b)) * 100 : 50}%`, background: colorMe }" />
              <span :style="{ flex: 1, background: colorMate }" />
            </div>
            <b class="num right">{{ points(row.b) }}</b>
            <div class="vs-label small muted">{{ row.label }}</div>
          </div>
          <p class="small ink-2 gap-line">
            Median qualifying gap over {{ s.gap_races }} races:
            <b>{{ s.median_gap_pct == null ? '–' : `${Math.abs(s.median_gap_pct).toFixed(3)}%` }}</b>
            <template v-if="s.median_gap_pct"> in favour of {{ s.median_gap_pct < 0 ? me.name : mate.name }}</template>.
          </p>
        </div>
        <div class="side right">
          <NuxtLink :to="`/drivers/${mate.id}`"><b>{{ mate.name }}</b></NuxtLink>
          <span class="swatch" :style="{ background: colorMate }" />
        </div>
      </div>

      <Panel title="Qualifying gap, race by race" note="Gap in the last session both set a time in. Bars below zero: the left driver was faster.">
        <Chart :option="gapChart" :height="300" :compact-height="260" label="Qualifying gap per race" share-id="quali-gap" />
      </Panel>
      <Panel title="Running score" :note="`Duels won minus duels lost, from ${me.name}'s side.`">
        <Chart :option="runningChart" :height="260" label="Running qualifying and race duel score" />
      </Panel>

      <Panel v-if="data.seasons.length > 1" title="By season" flush>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th>Year</th><th class="r hide-sm">Races</th><th class="c">Qualifying</th><th class="c">Race</th><th class="r hide-sm">Points</th><th class="r hide-md">Median gap</th></tr></thead>
            <tbody>
              <tr v-for="x in data.seasons" :key="x.year">
                <td><NuxtLink class="link" :to="`/seasons/${x.year}`"><b>{{ x.year }}</b></NuxtLink></td>
                <td class="r hide-sm">{{ x.races }}</td>
                <td><DuelBar :won="x.quali_won" :lost="x.quali_lost" /></td>
                <td><DuelBar :won="x.race_won" :lost="x.race_lost" /></td>
                <td class="r small hide-sm">{{ points(x.points_me) }}–{{ points(x.points_mate) }}</td>
                <td class="r hide-md">{{ pct(x.median_gap_pct) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Every race" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr><th>Race</th><th class="c">Q {{ me.abbreviation }}</th><th class="c">Q {{ mate.abbreviation }}</th><th class="r hide-sm">Gap</th><th class="c">R {{ me.abbreviation }}</th><th class="c">R {{ mate.abbreviation }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in data.races.slice().reverse()" :key="r.race_id">
                <td><NuxtLink class="link" :to="`/races/${r.year}/${r.round}`"><span class="hide-sm">{{ r.year }} {{ r.grand_prix }}</span><span class="only-sm">{{ r.year }} {{ r.abbreviation }}</span></NuxtLink></td>
                <td class="c" :class="{ win: r.quali_me != null && r.quali_mate != null && r.quali_me < r.quali_mate }">{{ r.quali_me ?? '–' }}</td>
                <td class="c" :class="{ win: r.quali_me != null && r.quali_mate != null && r.quali_mate < r.quali_me }">{{ r.quali_mate ?? '–' }}</td>
                <td class="r small hide-sm">{{ pct(r.gap_pct) }}</td>
                <td class="c" :class="{ win: r.race_me != null && r.race_mate != null && r.race_me < r.race_mate }" :title="r.reason_me ?? ''">{{ outcome(r.race_me, r.race_text_me) }}</td>
                <td class="c" :class="{ win: r.race_me != null && r.race_mate != null && r.race_mate < r.race_me }" :title="r.reason_mate ?? ''">{{ outcome(r.race_mate, r.race_text_mate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.versus {
  display: grid;
  grid-template-columns: 1fr minmax(0, 2.2fr) 1fr;
  align-items: center;
  gap: 16px;
}
.side {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
}
.side.right {
  justify-content: flex-end;
  text-align: right;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.vs-row {
  display: grid;
  grid-template-columns: 48px 1fr 48px;
  align-items: center;
  gap: 10px;
}
.vs-row .left {
  text-align: right;
}
.vs-label {
  grid-column: 2;
  text-align: center;
  margin-top: -6px;
}
.vs-bar {
  display: flex;
  gap: 2px;
  height: 12px;
  border-radius: 6px;
  overflow: hidden;
}
.gap-line {
  text-align: center;
}
.win {
  font-weight: 700;
  background: var(--accent-soft);
}
@media (max-width: 720px) {
  .versus {
    grid-template-columns: 1fr 1fr;
  }
  .rows {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
