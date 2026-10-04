<script setup lang="ts">
// Championship chances: who can still win, the simulated probability for each driver, and how the odds moved
// race by race through the season.
import type { EChartsOption, SeriesOption } from 'echarts'

interface Odds {
  available: boolean
  reason?: string
  finished: boolean
  current: {
    after_round: number
    remaining_races: number
    remaining_sprints: number
    drivers: { driver_id: string; name: string; points: number; probability: number; max_possible: number; can_still_win: boolean }[]
  }
  history: { round: number; abbreviation: string; odds: Record<string, number> }[]
}

const props = defineProps<{ year: number; teamOf: (id: string) => string }>()
const { data } = useFetch<Odds>(() => `/api/seasons/${props.year}/title-odds`, { server: false, key: `odds:${props.year}` })

const contenders = computed(() => (data.value?.current.drivers ?? []).filter((d) => d.can_still_win || d.probability > 0))
const names = computed(() => Object.fromEntries((data.value?.current.drivers ?? []).map((d) => [d.driver_id, d.name])))
const chart = useChartOption<EChartsOption>(() => {
  const h = data.value?.history ?? []
  const ids = [...new Set(h.flatMap((r) => Object.entries(r.odds).filter(([, p]) => p >= 0.05).map(([d]) => d)))]
  const styles = driverStyles(ids.map((d) => ({ driver_id: d, constructor_id: props.teamOf(d) })))
  return {
    animation: false,
    legend: { type: 'scroll', top: 0, left: 0, right: 0 },
    grid: { left: 8, right: 16, top: 40, bottom: 28, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${Math.round((v as number) * 100)}%` },
    xAxis: { type: 'category', data: h.map((r) => r.abbreviation), boundaryGap: false },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: { formatter: (v: number) => `${v * 100}%` } },
    series: ids.map((d) => ({
      name: names.value[d] ?? d,
      type: 'line',
      data: h.map((r) => r.odds[d] ?? 0),
      showSymbol: false,
      color: styles[d]!.color,
      lineStyle: { width: 2, type: styles[d]!.dashed ? [5, 3] : 'solid' },
    })) as SeriesOption[],
  }
})
</script>

<template>
  <Panel
    v-if="data?.available"
    id="title-odds"
    :title="data.finished ? 'How the title race unfolded' : 'Title chances'"
    :note="data.finished ? 'Each driver\'s chance of the title after every round, by simulating the rest of the season from their results so far.' : `After round ${data.current.after_round}, with ${data.current.remaining_races} race${data.current.remaining_races === 1 ? '' : 's'}${data.current.remaining_sprints ? ` and ${data.current.remaining_sprints} sprint${data.current.remaining_sprints === 1 ? '' : 's'}` : ''} left. 20,000 simulated finishes, each driver scoring like they have so far this season.`"
  >
    <div class="grid-12">
      <div v-if="!data.finished" class="span-5">
        <ol class="odds">
          <li v-for="d in contenders" :key="d.driver_id" :class="{ out: !d.can_still_win }">
            <NuxtLink :to="`/drivers/${d.driver_id}`" class="name"><b>{{ d.name }}</b></NuxtLink>
            <span class="bar"><span :style="{ width: `${d.probability * 100}%` }" /></span>
            <span class="pct num">{{ d.probability >= 0.995 ? '>99%' : d.probability < 0.005 ? (d.can_still_win ? '<1%' : 'Out') : `${Math.round(d.probability * 100)}%` }}</span>
            <span class="sub-line">{{ points(d.points) }} points · could still reach {{ points(d.max_possible) }}</span>
          </li>
        </ol>
        <p class="small muted">Out: cannot catch the leader even by winning everything left. A rough guide: races are simulated as independent.</p>
      </div>
      <div :class="data.finished ? 'span-12' : 'span-7'">
        <Chart :option="chart" :height="300" :compact-height="260" label="Title chances after each round" share-id="title-odds" />
      </div>
    </div>
  </Panel>
</template>

<style scoped>
.odds {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
}
.odds li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px 48px;
  gap: 4px 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--grid);
}
.odds li.out {
  opacity: 0.55;
}
.odds .sub-line {
  grid-column: 1 / -1;
  margin-top: -2px;
}
.bar {
  height: 8px;
  border-radius: 4px;
  background: var(--surface-3);
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  background: var(--series-1);
}
.pct {
  text-align: right;
  font-weight: 650;
}
</style>
