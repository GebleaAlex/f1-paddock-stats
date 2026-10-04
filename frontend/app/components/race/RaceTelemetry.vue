<script setup lang="ts">
// Compare the fastest laps of two drivers in any session of the weekend (2018+): track map coloured by the faster
// driver in each section with a replay, stacked speed/gap/throttle/brake/gear traces, and straight-line speed.
import type { Corner, TelemetryLap } from '~/utils/charts'

interface SessionLap { session_key: string; driver_id: string; name: string; abbreviation: string | null; lap: number; lap_time_ms: number; constructor_id: string | null }
interface Session { type: string; session_key: string; name: string; drivers: number; laps: SessionLap[] }
interface Straight { driver_id: string; name: string; abbreviation: string | null; constructor_id: string | null; lap_time_ms: number; top_speed_kmh: number; full_throttle_pct: number; clipping_m: number }
interface Compare {
  session: { type: string; name: string; rotation: number; corners: Corner[] }
  drivers: string[]
  laps: Record<string, TelemetryLap>
  delta?: number[]
  dominance?: { from_m: number; to_m: number; driver_id: string; times: Record<string, number> }[]
  straights: Record<string, { top_speed_kmh: number; full_throttle_pct: number; clipping_m: number }>
  corner_deltas?: { corners: CornerDelta[]; lap_gap_s: number | null; straights_s: number | null }
  gap_regions?: { from_m: number; to_m: number }[]
}
interface CornerDelta {
  corner: string
  apex_m: number
  from_m: number
  to_m: number
  gain_s: number
  min_speed: (number | null)[]
  brake_before_apex_m: (number | null)[]
  reliable: boolean
}

const props = defineProps<{ year: number; round: number }>()
const { data: sessions } = useFetch<Session[]>(() => `/api/races/${props.year}/${props.round}/sessions`, {
  server: false,
  key: `sessions:${props.year}:${props.round}`,
})
const sessionParam = useQueryState('session', '')
const aParam = useQueryState('a', '')
const bParam = useQueryState('b', '')
const session = computed(() => sessions.value?.find((s) => s.type === sessionParam.value) ?? sessions.value?.find((s) => s.type === 'Q') ?? sessions.value?.[0])
const lapsInSession = computed(() => session.value?.laps ?? [])
const a = computed(() => (lapsInSession.value.some((l) => l.driver_id === aParam.value) ? aParam.value : lapsInSession.value[0]?.driver_id ?? ''))
const b = computed(() => (lapsInSession.value.some((l) => l.driver_id === bParam.value) && bParam.value !== a.value ? bParam.value : lapsInSession.value.find((l) => l.driver_id !== a.value)?.driver_id ?? ''))

const sessionOptions = computed(() => (sessions.value ?? []).map((s) => ({ value: s.type, label: s.name })))
const best = computed(() => lapsInSession.value[0]?.lap_time_ms ?? 0)
const driverOptions = computed(() =>
  lapsInSession.value.map((l, i) => ({
    value: l.driver_id,
    label: l.name,
    sub: `${lapTime(l.lap_time_ms)}${i ? ` · +${((l.lap_time_ms - best.value) / 1000).toFixed(3)}s` : ' · fastest'}`,
  })),
)
const sessionModel = computed({ get: () => session.value?.type ?? '', set: (v: string) => (sessionParam.value = v) })
const aModel = computed({ get: () => a.value, set: (v: string) => (aParam.value = v) })
const bModel = computed({ get: () => b.value, set: (v: string) => (bParam.value = v) })

const url = computed(() => (session.value && a.value ? `/api/races/${props.year}/${props.round}/telemetry?session=${session.value.type}&drivers=${[a.value, b.value].filter(Boolean).join(',')}` : ''))
const { data: cmp, pending } = useFetch<Compare>(() => url.value || '/api/health', {
  server: false,
  watch: [url],
  key: () => `tel:${url.value}`,
})
const { data: straights } = useFetch<{ rows: Straight[] }>(
  () => `/api/races/${props.year}/${props.round}/straights?session=${session.value?.type ?? 'Q'}`,
  { server: false, watch: [() => session.value?.type], key: () => `str:${props.year}:${props.round}:${session.value?.type}` },
)

const ready = computed(() => !!cmp.value && 'laps' in (cmp.value as object))
const laps = computed(() => (ready.value ? cmp.value!.drivers.map((d) => cmp.value!.laps[d]!) : []))
const colors = computed(() => [seriesColor(1), seriesColor(2)])
const templateColors = [seriesVar(1), seriesVar(2)]
// Corner by corner: which corner was picked in the table (highlighted on the chart), and the table order.
const focusCorner = ref<string | null>(null)
watch(url, () => (focusCorner.value = null))
const cornerOrder = useQueryState('corners', 'lap')
const corners = computed(() => cmp.value?.corner_deltas?.corners ?? [])
const sortedCorners = computed(() =>
  cornerOrder.value === 'biggest'
    ? corners.value.slice().sort((x, y) => Number(y.reliable) - Number(x.reliable) || Math.abs(y.gain_s) - Math.abs(x.gain_s))
    : corners.value,
)
const maxGain = computed(() => Math.max(0.05, ...corners.value.filter((c) => c.reliable).map((c) => Math.abs(c.gain_s))))
const cornerTotals = computed(() => {
  const cd = cmp.value?.corner_deltas
  if (!cd || cd.lap_gap_s == null) return null
  return { corners: cd.lap_gap_s - (cd.straights_s ?? 0), straights: cd.straights_s ?? 0 }
})
const chart = useChartOption(() => {
  if (!ready.value) return {}
  const focus = corners.value.find((c) => c.corner === focusCorner.value)
  return telemetryOption(laps.value, cmp.value!.delta, cmp.value!.session.corners, colors.value, {
    focus: focus ? [focus.from_m, focus.to_m] : null,
    gaps: (cmp.value!.gap_regions ?? []).map((g) => [g.from_m, g.to_m] as [number, number]),
  })
})
/** "+0.12 s" in favour of whichever driver was quicker; gain_s > 0 means the first driver was quicker. */
function gainText(g: number) {
  if (Math.abs(g) < 0.005) return 'level'
  const who = g > 0 ? laps.value[0] : laps.value[1]
  return `${who?.abbreviation ?? who?.name} +${Math.abs(g).toFixed(2)} s`
}
function speedText(v: number | null | undefined) {
  return v == null ? '–' : `${Math.round(v)}`
}
const sectorsWon = computed(() => {
  const out: Record<string, number> = {}
  for (const s of cmp.value?.dominance ?? []) out[s.driver_id] = (out[s.driver_id] ?? 0) + 1
  return out
})
function sector(ms: number | null | undefined) {
  return ms ? (ms / 1000).toFixed(3) : '–'
}
const is2026 = computed(() => props.year >= 2026)
</script>

<template>
  <div class="stack">
    <div v-if="sessions && !sessions.length" class="panel">
      <EmptyState title="No telemetry for this race yet" text="Car telemetry covers 2018 onwards and is added a few sessions at a time." />
    </div>
    <template v-else-if="sessions">
      <div class="filters">
        <UiChoice v-model="sessionModel" label="Session" :options="sessionOptions" />
        <UiSelect v-model="aModel" label="Driver" :options="driverOptions" searchable />
        <span class="vs small muted">vs</span>
        <UiSelect v-model="bModel" label="Driver" :options="driverOptions" searchable />
      </div>

      <div v-if="ready" class="cards">
        <div v-for="(lap, i) in laps" :key="lap.driver_id" class="lap-card panel">
          <div class="spread">
            <div class="row">
              <span class="swatch" :style="{ background: templateColors[i] }" />
              <NuxtLink :to="`/drivers/${lap.driver_id}`"><b>{{ lap.name }}</b></NuxtLink>
            </div>
            <span class="small muted">Lap {{ lap.lap }}</span>
          </div>
          <div class="time">{{ lapTime(lap.lap_time_ms) }}</div>
          <div class="small ink-2 num">
            S1 {{ sector(lap.sectors?.s1_ms) }} · S2 {{ sector(lap.sectors?.s2_ms) }} · S3 {{ sector(lap.sectors?.s3_ms) }}
          </div>
          <div v-if="lap.telemetry_gaps" class="small warn-line">The speed trace drops out in places on this lap (shaded grey); the laps are matched by position on track instead.</div>
          <div class="small muted">
            <template v-if="lap.sectors?.compound">{{ compound(lap.sectors.compound).label }} tyres<template v-if="lap.sectors.tyre_life">, {{ lap.sectors.tyre_life }} laps old</template> · </template>
            Top speed {{ cmp!.straights[lap.driver_id]?.top_speed_kmh }} km/h
            <template v-if="cmp!.dominance"> · fastest in {{ sectorsWon[lap.driver_id] ?? 0 }} of {{ cmp!.dominance.length }} sections</template>
          </div>
        </div>
        <div v-if="laps.length === 2" class="gap panel">
          <span class="small muted">Gap</span>
          <b class="big">{{ ((laps[1]!.lap_time_ms - laps[0]!.lap_time_ms) / 1000).toFixed(3) }}s</b>
          <span class="small ink-2">{{ laps[1]!.lap_time_ms >= laps[0]!.lap_time_ms ? laps[0]!.abbreviation : laps[1]!.abbreviation }} faster</span>
        </div>
      </div>

      <div class="grid-12">
        <Panel class="span-5" title="Track map" note="Each section is coloured by the faster driver. Press play to replay both laps.">
          <RaceTrackMap v-if="ready" :laps="laps" :rotation="cmp!.session.rotation" :corners="cmp!.session.corners" :dominance="cmp!.dominance" :colors="templateColors" />
          <div v-else class="skeleton" style="aspect-ratio: 1.15" />
        </Panel>
        <Panel class="span-7" title="Telemetry" :note="laps.length === 2 ? `Gap: time ${laps[1]?.abbreviation} is behind ${laps[0]?.abbreviation} at each point; it grows where ${laps[0]?.abbreviation} is quicker.` : 'Speed, throttle, brake and gear along the lap.'">
          <Chart v-if="ready" :option="chart" :height="620" :compact-height="560" label="Speed, gap, throttle, brake and gear along the lap" share-id="telemetry" />
          <div v-else class="skeleton" style="height: 620px" />
          <p v-if="pending" class="small muted">Loading laps…</p>
        </Panel>
      </div>

      <Panel
        v-if="ready && laps.length === 2 && corners.length"
        title="Corner by corner"
        :note="cornerTotals ? `Where the ${Math.abs(cmp!.corner_deltas!.lap_gap_s!).toFixed(3)} s between the laps was made: ${Math.abs(cornerTotals.corners).toFixed(2)} s through the corners (braking zone to exit), ${Math.abs(cornerTotals.straights).toFixed(2)} s on the straights, each in favour of whoever was quicker there. Tap a corner to highlight it on the chart; differences of a few hundredths are within the precision of the data.${['R', 'S'].includes(cmp!.session.type) ? ' These are race laps, often driven on different laps: traffic, slipstream and DRS can make one corner look very different.' : ''}` : ''"
        flush
      >
        <template #actions>
          <UiChoice v-model="cornerOrder" label="Order" :options="[{ value: 'lap', label: 'Lap order' }, { value: 'biggest', label: 'Biggest gaps' }]" />
        </template>
        <div class="tot">
          <span><b>Corners:</b> {{ cornerTotals ? gainText(cornerTotals.corners) : '' }}</span>
          <span><b>Straights:</b> {{ cornerTotals ? gainText(cornerTotals.straights) : '' }}</span>
        </div>
        <div class="table-scroll">
          <table class="data corners">
            <thead>
              <tr>
                <th>Corner</th>
                <th class="bar-col">Time gained</th>
                <th class="r">Min speed <span class="muted">km/h</span></th>
                <th class="r hide-sm">Brakes before apex</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in sortedCorners"
                :key="c.corner"
                :class="{ focus: focusCorner === c.corner, unreliable: !c.reliable }"
                tabindex="0"
                @click="focusCorner = focusCorner === c.corner ? null : c.corner"
                @keydown.enter="focusCorner = focusCorner === c.corner ? null : c.corner"
              >
                <td class="nowrap"><b>Turn {{ c.corner }}</b><span class="sub-line">{{ (c.apex_m / 1000).toFixed(2) }} km</span></td>
                <td class="bar-col">
                  <template v-if="c.reliable">
                    <div class="diverge" :aria-label="gainText(c.gain_s)">
                      <span class="half left"><span v-if="c.gain_s > 0" :style="{ width: `${(c.gain_s / maxGain) * 100}%`, background: templateColors[0] }" /></span>
                      <span class="half right"><span v-if="c.gain_s < 0" :style="{ width: `${(-c.gain_s / maxGain) * 100}%`, background: templateColors[1] }" /></span>
                    </div>
                    <span class="small num">{{ gainText(c.gain_s) }}</span>
                  </template>
                  <span v-else class="small muted">Telemetry gap, not measured</span>
                </td>
                <td class="r num nowrap">{{ speedText(c.min_speed[0]) }} <span class="muted">/</span> {{ speedText(c.min_speed[1]) }}</td>
                <td class="r num nowrap hide-sm">
                  <template v-if="c.brake_before_apex_m[0] == null && c.brake_before_apex_m[1] == null"><span class="muted">flat out</span></template>
                  <template v-else>{{ c.brake_before_apex_m[0] ?? '–' }} <span class="muted">/</span> {{ c.brake_before_apex_m[1] ?? '–' }} m</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="tiny muted legend-line">
          <span class="swatch" :style="{ background: templateColors[0] }" /> {{ laps[0]?.name }} quicker
          <span class="swatch" :style="{ background: templateColors[1], marginLeft: '12px' }" /> {{ laps[1]?.name }} quicker · speeds and braking points: {{ laps[0]?.abbreviation }} / {{ laps[1]?.abbreviation }}
        </p>
      </Panel>

      <Panel
        v-if="straights?.rows.length"
        title="Straight-line speed"
        :note="is2026 ? 'Clipping is the distance a car slows down while still at full throttle, mostly because the battery has stopped deploying. It became a big factor with the 2026 power units.' : 'Top speed and share of the fastest lap spent at full throttle. Clipping is the distance a car slows down while still at full throttle.'"
        flush
      >
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr><th>Driver</th><th class="r">Top speed</th><th class="r hide-sm">Full throttle</th><th class="r">Clipping</th><th class="r hide-sm">Lap</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in straights.rows" :key="r.driver_id">
                <td><TeamName v-if="r.constructor_id" :id="r.constructor_id" :name="r.name" :link="false" /><span v-else>{{ r.name }}</span></td>
                <td class="r num"><b>{{ r.top_speed_kmh }}</b> km/h</td>
                <td class="r num hide-sm">{{ r.full_throttle_pct }}%</td>
                <td class="r num">{{ r.clipping_m }} m</td>
                <td class="r num hide-sm">{{ lapTime(r.lap_time_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </template>
    <div v-else class="panel"><div class="skeleton" style="height: 420px" /></div>
  </div>
</template>

<style scoped>
.tot {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  padding: 0 var(--pad) 10px;
  font-size: 13px;
}
.corners tbody tr {
  cursor: pointer;
}
.corners tbody tr:hover {
  background: var(--surface-2);
}
.corners tbody tr.focus {
  background: var(--accent-soft);
}
.corners tr.unreliable td {
  color: var(--muted);
}
.bar-col {
  min-width: 200px;
}
.diverge {
  display: inline-flex;
  width: 140px;
  height: 10px;
  margin-right: 10px;
  vertical-align: middle;
}
.half {
  flex: 1;
  display: flex;
  background: var(--surface-2);
}
.half.left {
  justify-content: flex-end;
  border-right: 1px solid var(--axis);
  border-radius: 3px 0 0 3px;
}
.half.right {
  border-radius: 0 3px 3px 0;
}
.half > span {
  display: block;
  height: 100%;
  border-radius: 3px;
}
.legend-line {
  padding: 8px var(--pad) 12px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.warn-line {
  border-left: 3px solid var(--warning);
  padding-left: 8px;
  color: var(--ink-2);
}
@media (max-width: 640px) {
  .diverge {
    width: 80px;
  }
  .bar-col {
    min-width: 0;
  }
}
.vs {
  flex: none !important;
}
.cards {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 12px;
}
.lap-card {
  gap: 4px;
}
.time {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.gap {
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 140px;
}
.big {
  font-size: 26px;
}
@media (max-width: 900px) {
  .cards {
    grid-template-columns: 1fr 1fr;
  }
  .gap {
    grid-column: 1 / -1;
    flex-direction: row;
    gap: 10px;
  }
}
@media (max-width: 640px) {
  .cards {
    grid-template-columns: 1fr;
  }
}
</style>
