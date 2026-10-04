<script setup lang="ts">
// Race pace of up to four drivers: lap times (optionally fuel-corrected, green-flag laps only), tyre colours from
// 2018, and a stint table with each set's pace and wear.
import type { PaceLap, Period, StrategyDriver } from '~/utils/charts'

const props = defineProps<{ year: number; round: number; drivers: string[]; names: Record<string, string> }>()

const mode = useQueryState('pace', 'corrected')
const laps = useQueryState('laps', 'clean')
const MODES = [
  { value: 'corrected', label: 'Fuel-corrected', sub: 'Removes the effect of the car getting lighter' },
  { value: 'raw', label: 'Raw lap times' },
]
const LAPS = [
  { value: 'clean', label: 'Racing laps', sub: 'No lap 1, pit laps, safety cars or slow laps' },
  { value: 'all', label: 'All laps' },
]

const { data } = useFetch<{ has_timing: boolean; laps: Record<string, PaceLap[]>; periods: Period[] }>(
  () => `/api/races/${props.year}/${props.round}/pace?drivers=${props.drivers.join(',')}`,
  { server: false, key: `pace:${props.year}:${props.round}:${props.drivers.join(',')}`, watch: [() => props.drivers.join(',')] },
)
const { data: strategy } = useFetch<{ drivers: StrategyDriver[]; method: { fuel_start_kg: number; fuel_s_per_kg: number } }>(
  () => `/api/races/${props.year}/${props.round}/strategy`,
  { server: false, key: `strategy:${props.year}:${props.round}` },
)

const chart = useChartOption(() =>
  data.value
    ? paceOption(data.value.laps, props.names, props.drivers, props.drivers.map((_, i) => seriesColor(i + 1)), {
        corrected: mode.value === 'corrected',
        cleanOnly: laps.value === 'clean',
        periods: data.value.periods,
      })
    : {},
)
const stints = computed(() =>
  props.drivers.flatMap((id, i) =>
    (strategy.value?.drivers.find((d) => d.driver_id === id)?.stints ?? []).map((s) => ({ ...s, id, slot: i + 1 })),
  ),
)
</script>

<template>
  <div class="stack">
    <Panel
      title="Race pace"
      :note="mode === 'corrected' && strategy ? `Corrected for fuel: about ${strategy.method.fuel_start_kg} kg at the start, ${strategy.method.fuel_s_per_kg} s per kg per lap.` : 'Lap times as driven.'"
    >
      <template #actions>
        <UiChoice v-model="mode" label="Times" :options="MODES" />
        <UiChoice v-model="laps" label="Laps" :options="LAPS" />
      </template>
      <Chart v-if="data" :option="chart" :height="440" :compact-height="340" label="Lap times of the chosen drivers" share-id="pace" />
      <div v-else class="skeleton" style="height: 440px" />
      <p v-if="data?.has_timing" class="small muted">Dots are coloured by tyre: <span v-for="c in ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']" :key="c" class="tyre"><span class="swatch" :style="{ background: compound(c).color }" /> {{ compound(c).label }}</span></p>
    </Panel>

    <Panel v-if="stints.length && strategy" title="Stints" note="Pace is the median fuel-corrected racing lap; wear is how much slower each lap got as the tyres aged (needs five racing laps)." flush>
      <div class="table-scroll">
        <table class="data">
          <thead>
            <tr><th>Driver</th><th>Tyre</th><th class="r">Laps</th><th class="r hide-sm">Racing laps</th><th class="r">Pace</th><th class="r">Wear per lap</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in stints" :key="`${s.id}-${s.stint}`">
              <td class="nowrap"><span class="swatch" :style="{ background: seriesVar(s.slot), marginRight: '6px' }" />{{ names[s.id] ?? s.id }}</td>
              <td class="nowrap">
                <span v-if="s.compound" class="tyre"><span class="swatch" :style="{ background: compound(s.compound).color }" /> {{ compound(s.compound).label }}</span>
                <span v-else class="muted">Stint {{ s.stint }}</span>
                <span v-if="s.tyre_age_at_start" class="tiny muted"> · used ({{ s.tyre_age_at_start }})</span>
              </td>
              <td class="r num nowrap">{{ s.from_lap }}–{{ s.to_lap }}</td>
              <td class="r hide-sm">{{ s.clean_laps ?? '–' }}</td>
              <td class="r num">{{ s.median_corrected_ms ? lapTime(s.median_corrected_ms) : '–' }}</td>
              <td class="r num">{{ s.degradation_s_per_lap != null ? `${s.degradation_s_per_lap > 0 ? '+' : ''}${s.degradation_s_per_lap.toFixed(3)}s` : '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  </div>
</template>

<style scoped>
.tyre {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-right: 10px;
}
</style>
