<script setup lang="ts">
// Qualifying from the timing data (2018+): every driver's best lap and best sectors, the ideal lap those sectors
// add up to, and the time each driver left on the table.
interface Row {
  driver_id: string
  name: string
  abbreviation: string | null
  constructor_id: string | null
  best_ms: number
  s1_ms: number | null
  s2_ms: number | null
  s3_ms: number | null
  ideal_ms: number | null
  gap_ms: number
  left_on_table_ms: number | null
  top_speed: number | null
  laps: number
  sector_best: string[]
}

const props = defineProps<{ year: number; round: number; session?: string }>()
const { data } = useFetch<{ rows: Row[]; ideal_order: string[] }>(
  () => `/api/races/${props.year}/${props.round}/qualifying-analysis?session=${props.session ?? 'Q'}`,
  { server: false, key: `qa:${props.year}:${props.round}:${props.session ?? 'Q'}` },
)
const pole = computed(() => data.value?.rows[0]?.best_ms ?? 0)
// Bars are scaled to the tenth-fastest gap so the front of the grid is readable; slower laps fill the bar.
const maxGap = computed(() => Math.max(100, data.value?.rows[Math.min(9, (data.value?.rows.length ?? 1) - 1)]?.gap_ms ?? 1000))
const fastestIdeal = computed(() => data.value?.rows.find((r) => r.driver_id === data.value?.ideal_order[0]))
function sec(ms: number | null) {
  return ms ? (ms / 1000).toFixed(3) : '–'
}
</script>

<template>
  <Panel
    v-if="data?.rows.length"
    title="Best sectors and ideal laps"
    :note="fastestIdeal ? `Purple marks the fastest sector of the session. The ideal lap adds up a driver's three best sectors; ${fastestIdeal.name} had the best one, ${lapTime(fastestIdeal.ideal_ms)}.` : 'Purple marks the fastest sector of the session.'"
    flush
  >
    <div class="table-scroll">
      <table class="data">
        <thead>
          <tr>
            <th class="r">#</th><th>Driver</th><th class="r">Best lap</th><th class="hide-sm">Gap to pole</th>
            <th class="r hide-md">S1</th><th class="r hide-md">S2</th><th class="r hide-md">S3</th>
            <th class="r">Ideal</th><th class="r hide-sm">Left on table</th><th class="r hide-md">Top speed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in data.rows" :key="r.driver_id">
            <td class="r muted">{{ i + 1 }}</td>
            <td class="nowrap"><TeamName v-if="r.constructor_id" :id="r.constructor_id" :name="r.name" :link="false" /><span v-else>{{ r.name }}</span></td>
            <td class="r num"><b>{{ lapTime(r.best_ms) }}</b></td>
            <td class="hide-sm">
              <div class="gap-cell">
                <span class="track"><span class="bar" :style="{ width: `${Math.min(1, r.gap_ms / maxGap) * 100}%` }" /></span>
                <span class="small num">{{ i ? `+${(r.gap_ms / 1000).toFixed(3)}` : 'Pole' }}</span>
              </div>
            </td>
            <td class="r num hide-md" :class="{ best: r.sector_best.includes('s1_ms') }">{{ sec(r.s1_ms) }}</td>
            <td class="r num hide-md" :class="{ best: r.sector_best.includes('s2_ms') }">{{ sec(r.s2_ms) }}</td>
            <td class="r num hide-md" :class="{ best: r.sector_best.includes('s3_ms') }">{{ sec(r.s3_ms) }}</td>
            <td class="r num">{{ r.ideal_ms ? lapTime(r.ideal_ms) : '–' }}</td>
            <td class="r num hide-sm">{{ r.left_on_table_ms ? `${(r.left_on_table_ms / 1000).toFixed(3)}s` : '–' }}</td>
            <td class="r num hide-md">{{ r.top_speed ? `${Math.round(r.top_speed)}` : '–' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="small muted foot">Pole lap {{ lapTime(pole) }}. Sector times come from the official timing, so they may not add up exactly to the lap time.</p>
  </Panel>
</template>

<style scoped>
.gap-cell {
  min-width: 170px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.track {
  width: 100px;
  flex: none;
}
.bar {
  display: block;
  height: 8px;
  border-radius: 0 4px 4px 0;
  background: var(--series-1);
  min-width: 2px;
}
td.best {
  color: var(--sector-best);
  font-weight: 700;
}
.foot {
  padding: 0 var(--pad) var(--pad);
}
</style>
