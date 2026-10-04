<script setup lang="ts">
// The whole field ranked by race pace: the median fuel-corrected green-flag lap, the spread of those laps (middle
// half) and the gap to the teammate. Clicking a driver adds them to the lap-time chart below.
interface PaceRow {
  rank: number
  driver_id: string
  name: string
  abbreviation: string | null
  constructor_id: string
  constructor: string
  position: number | null
  position_text: string
  laps: number
  median_s: number
  q25_s: number
  q75_s: number
  gap_s: number
  teammate: { driver_id: string; gap_s: number } | null
}
interface PaceRanking {
  has_timing: boolean
  rows: PaceRow[]
  too_few_laps: string[]
  method: { min_laps: number }
}

const props = defineProps<{ year: number; round: number; picked: string[] }>()
const emit = defineEmits<{ toggle: [id: string] }>()
const { data } = useFetch<PaceRanking>(() => `/api/races/${props.year}/${props.round}/pace-ranking`, {
  server: false,
  key: `pace-ranking:${props.year}:${props.round}`,
})

const rows = computed(() => data.value?.rows ?? [])
const best = computed(() => rows.value[0]?.median_s ?? 0)
// The scale runs from the best median to the slowest upper quartile, capped so one slow car does not squash the rest.
const span = computed(() => Math.min(4, Math.max(1, ...rows.value.map((r) => r.q75_s - best.value))))
const lo = computed(() => Math.min(0, ...rows.value.map((r) => r.q25_s - best.value)))
const at = (s: number) => `${Math.min(100, Math.max(0, ((s - best.value - lo.value) / (span.value - lo.value)) * 100))}%`
const names = computed(() => Object.fromEntries(rows.value.map((r) => [r.driver_id, r.abbreviation || r.name])))
const name = (r: PaceRow) => r.abbreviation || r.name
</script>

<template>
  <Panel
    title="Race pace ranking"
    :note="`Median of each driver's green-flag laps with the weight of fuel taken out; the bar is the middle half of those laps. ${data?.has_timing ? 'Safety-car laps, ' : ''}in- and out-laps and lap 1 are left out. Tap a driver to add them to the chart below.`"
    flush
  >
    <div v-if="!data" class="skeleton" style="height: 420px; margin: 0 var(--pad) var(--pad)" />
    <EmptyState v-else-if="!rows.length" title="Not enough laps" :text="`Drivers need at least ${data.method.min_laps} green-flag laps to be ranked.`" />
    <template v-else>
      <ol class="board">
        <li v-for="r in rows" :key="r.driver_id">
          <button
            type="button"
            class="row-btn"
            :class="{ on: picked.includes(r.driver_id) }"
            :aria-pressed="picked.includes(r.driver_id)"
            :title="picked.includes(r.driver_id) ? `Remove ${r.name} from the chart` : `Add ${r.name} to the chart`"
            @click="emit('toggle', r.driver_id)"
          >
            <span class="rank num">{{ r.rank }}</span>
            <span class="who">
              <span class="nm"><span class="swatch" :style="{ background: teamColor(r.constructor_id) }" /><b>{{ r.name }}</b></span>
              <span class="sub-line">
                {{ r.position ? `Finished P${r.position}` : r.position_text }} · {{ r.laps }} laps
                <template v-if="r.teammate"> · {{ r.teammate.gap_s <= 0 ? `${Math.abs(r.teammate.gap_s).toFixed(2)} s/lap faster than` : `${r.teammate.gap_s.toFixed(2)} s/lap slower than` }} {{ names[r.teammate.driver_id] }}</template>
              </span>
            </span>
            <span class="scale" role="img" :aria-label="`Median ${r.gap_s.toFixed(3)} s off the best, middle half of laps from ${(r.q25_s - best).toFixed(2)} to ${(r.q75_s - best).toFixed(2)} s`">
              <span class="zero" :style="{ left: at(best) }" />
              <span class="range" :style="{ left: at(r.q25_s), width: `calc(${at(r.q75_s)} - ${at(r.q25_s)})` }" />
              <span class="marker" :style="{ left: at(r.median_s) }" />
            </span>
            <span class="value num">{{ r.rank === 1 ? lapTime(r.median_s * 1000) : `+${r.gap_s.toFixed(3)}` }}</span>
          </button>
        </li>
      </ol>
      <p v-if="data.too_few_laps.length" class="tiny muted foot">Not ranked, fewer than {{ data.method.min_laps }} green-flag laps: {{ data.too_few_laps.join(', ') }}.</p>
    </template>
  </Panel>
</template>

<style scoped>
.board {
  list-style: none;
  margin: 0;
  padding: 0 0 6px;
}
.row-btn {
  display: grid;
  grid-template-columns: 28px minmax(0, 1.5fr) minmax(0, 2fr) 72px;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 8px var(--pad);
  border: 0;
  border-bottom: 1px solid var(--grid);
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
li:last-child .row-btn {
  border-bottom: 0;
}
.row-btn:hover {
  background: var(--surface-2);
}
.row-btn.on {
  background: var(--accent-soft);
}
.rank {
  color: var(--muted);
  text-align: right;
  font-weight: 600;
}
.who {
  min-width: 0;
}
.nm {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.scale {
  position: relative;
  height: 18px;
}
.zero {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--axis);
}
.range {
  position: absolute;
  top: 6px;
  height: 6px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--series-1) 30%, transparent);
}
.marker {
  position: absolute;
  top: 3px;
  width: 12px;
  height: 12px;
  margin-left: -6px;
  border-radius: 50%;
  background: var(--series-1);
  border: 2px solid var(--surface);
}
.value {
  text-align: right;
  font-weight: 650;
}
.foot {
  padding: 4px var(--pad) 10px;
  margin: 0;
}
@media (max-width: 640px) {
  .row-btn {
    grid-template-columns: 24px minmax(0, 1fr) 64px;
  }
  .scale {
    grid-column: 2 / -1;
    grid-row: 2;
  }
}
</style>
