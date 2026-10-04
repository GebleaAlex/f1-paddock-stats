<script setup lang="ts">
// Tyre strategy for every driver, the time a pit stop cost at this race, and which undercuts and overcuts worked.
import type { Period, StrategyDriver } from '~/utils/charts'

interface Battle {
  early: string
  late: string
  early_lap: number
  late_lap: number
  verdict: 'undercut worked' | 'overcut worked' | 'undercut failed' | 'overcut failed'
  winner: string
  gap_before_s: number
  gap_after_s: number
}
interface Strategy {
  has_timing: boolean
  has_stops: boolean
  total_laps: number
  drivers: StrategyDriver[]
  compounds: string[]
  periods: Period[]
  pit_loss_s: number | null
  pit_loss_samples: number
  battles: Battle[]
}

const props = defineProps<{ year: number; round: number; circuitId: string }>()
const { data } = useFetch<Strategy>(() => `/api/races/${props.year}/${props.round}/strategy`, {
  server: false,
  key: `strategy:${props.year}:${props.round}`,
})
const { data: circuitLoss } = useFetch<{ typical_s: number | null }>(() => `/api/circuits/${props.circuitId}/pit-loss`, {
  server: false,
  key: `pitloss:${props.circuitId}`,
})

const chart = useChartOption(() => (data.value ? strategyOption(data.value.drivers, data.value.total_laps, data.value.periods) : {}))
const names = computed(() => Object.fromEntries((data.value?.drivers ?? []).map((d) => [d.driver_id, d.name])))
const worked = computed(() => (data.value?.battles ?? []).filter((b) => b.verdict.endsWith('worked')).length)
const stops = computed(() => (data.value?.drivers ?? []).reduce((n, d) => n + Math.max(0, d.stints.length - 1), 0))
const common = computed(() => {
  const counts = new Map<number, number>()
  for (const d of data.value?.drivers ?? []) counts.set(d.stints.length - 1, (counts.get(d.stints.length - 1) ?? 0) + 1)
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
  return top ? top[0] : null
})
</script>

<template>
  <div v-if="data" class="stack">
    <Tiles>
      <StatTile :label="data.has_timing ? 'Tyre changes' : 'Pit stops'" :value="stops" :hint="common != null ? `Most drivers stopped ${common === 1 ? 'once' : `${common} times`}` : ''" />
      <StatTile label="Time lost per stop" :value="data.pit_loss_s != null ? `${data.pit_loss_s}s` : '–'" :hint="data.pit_loss_samples ? `Median of ${data.pit_loss_samples} green-flag stops` : 'Not enough green-flag stops'" />
      <StatTile label="Usual here" :value="circuitLoss?.typical_s != null ? `${circuitLoss.typical_s}s` : '–'" hint="Median of every race at this circuit" />
      <StatTile label="Undercuts and overcuts" :value="data.battles.length" :hint="data.battles.length ? `${worked} gained a place` : 'None between cars running together'" />
    </Tiles>

    <Panel title="Tyre strategy" :note="data.has_timing ? 'Each bar is a driver in finishing order, each segment a set of tyres. Hover for tyre age and wear.' : 'Stints between pit stops. Tyre compounds are recorded from 2018.'">
      <div v-if="data.compounds.length" class="compounds">
        <span v-for="c in data.compounds" :key="c" class="chip"><span class="swatch" :style="{ background: compound(c).color }" />{{ compound(c).label }}</span>
      </div>
      <Chart :option="chart" :height="Math.max(360, data.drivers.length * 26)" :compact-height="Math.max(360, data.drivers.length * 24)" label="Tyre strategy for every driver" share-id="strategy" />
    </Panel>

    <Panel title="Undercuts and overcuts" note="Cars running next to each other, within four seconds, when one stopped first and the other within six laps. Decided by the order after both stops; stops under a safety car are left out." flush>
      <div v-if="data.battles.length" class="table-scroll">
        <table class="data">
          <thead>
            <tr><th class="r">Laps</th><th>Stopped first</th><th>Stopped later</th><th>Result</th><th class="r hide-sm">Gap before</th><th class="r hide-sm">Gap after</th></tr>
          </thead>
          <tbody>
            <tr v-for="b in data.battles" :key="`${b.early}-${b.late}-${b.early_lap}`">
              <td class="r num nowrap">{{ b.early_lap }}→{{ b.late_lap }}</td>
              <td :class="{ 'strong-cell': b.winner === b.early }">{{ names[b.early] }}</td>
              <td :class="{ 'strong-cell': b.winner === b.late }">{{ names[b.late] }}</td>
              <td><span class="verdict" :class="b.verdict.endsWith('worked') ? 'ok' : 'no'">{{ b.verdict }}</span></td>
              <td class="r hide-sm num">{{ b.gap_before_s > 0 ? `${b.gap_before_s.toFixed(1)}s behind` : `${(-b.gap_before_s).toFixed(1)}s ahead` }}</td>
              <td class="r hide-sm num">{{ b.gap_after_s > 0 ? `${b.gap_after_s.toFixed(1)}s behind` : `${(-b.gap_after_s).toFixed(1)}s ahead` }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else :title="data.has_stops ? 'No close pit-stop battles' : 'No pit stop data'" :text="data.has_stops ? 'No two cars running together stopped within six laps of each other.' : 'Pit stop laps are recorded from 2011.'" />
    </Panel>

    <RaceSimulator v-if="data.has_timing" :year="year" :round="round" :drivers="data.drivers" />
  </div>
  <div v-else class="panel"><div class="skeleton" style="height: 480px" /></div>
</template>

<style scoped>
.compounds {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.verdict {
  font-size: 12px;
  font-weight: 650;
  padding: 2px 8px;
  border-radius: 99px;
  white-space: nowrap;
}
.verdict.ok {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.verdict.no {
  background: var(--surface-3);
  color: var(--ink-2);
}
</style>
