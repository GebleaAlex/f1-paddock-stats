<script setup lang="ts">
// "What if he had stopped two laps earlier?" Change one driver's stop laps and tyres and see the modelled result.
// The model is fitted on this race (backend/paddock/simulator.py); everyone else keeps their real race.
import type { EChartsOption, SeriesOption } from 'echarts'
import type { Period, StrategyDriver } from '~/utils/charts'

interface PlanStint {
  compound: string
  from_lap: number
  to_lap: number
  age_start: number
}
interface Simulation {
  driver: string
  drivers: string[]
  last_lap: number
  pit_loss_s: number
  pit_loss_measured: boolean
  dry_race: boolean
  model: {
    reference: string
    compounds: Record<string, { offset_s: number; wear_s_per_lap: number; laps: number }>
    left_out: string[]
    laps: number
    rmse_s: number
  }
  actual: PlanStint[]
  plan: PlanStint[]
  time_change_s: number
  position: { real: number | null; simulated: number | null }
  ahead: { driver_id: string; gap_s: number } | null
  behind: { driver_id: string; gap_s: number } | null
  laps: { lap: number; delta_s: number; real: number | null; simulated: number | null }[]
  best: { stops: number[]; time_change_s: number }
  periods: Period[]
  warnings: string[]
  method: { pit_factor: Record<string, number> }
}

const props = defineProps<{ year: number; round: number; drivers: StrategyDriver[] }>()
const names = computed(() => Object.fromEntries(props.drivers.map((d) => [d.driver_id, d.name])))
const short = (id: string | undefined) => (id ? (names.value[id] ?? id).split(' ').at(-1) : '')

// The plan lives in the link (?who=&stops=&tyres=), so a "what if" can be shared.
const route = useRoute()
const router = useRouter()
const param = (k: string) => (typeof route.query[k] === 'string' ? (route.query[k] as string) : '')
const driver = ref(param('who'))
const stops = ref<number[]>(param('stops') ? param('stops').split(',').map(Number).filter(Number.isFinite) : [])
const compounds = ref<string[]>(param('tyres') ? param('tyres').toUpperCase().split(',') : [])
const edited = ref(!!param('tyres'))

function request(): Record<string, string> {
  const q: Record<string, string> = {}
  if (driver.value) q.driver = driver.value
  if (edited.value) {
    q.stops = stops.value.join(',')
    q.compounds = compounds.value.join(',')
  }
  return q
}
// The request follows the plan, a moment after the last change so that holding "+" does not send a request per lap.
const query = ref<Record<string, string>>(request())
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  [driver, stops, compounds, edited],
  () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      query.value = request()
      const next = { ...route.query }
      delete next.who
      delete next.stops
      delete next.tyres
      if (edited.value || (driver.value && driver.value !== sim.value?.drivers[0])) next.who = driver.value
      if (edited.value) {
        next.stops = stops.value.join(',')
        next.tyres = compounds.value.join(',').toLowerCase()
      }
      router.replace({ query: next })
    }, 250)
  },
  { deep: true },
)
const { data: fetched, error, status } = useFetch<Simulation>(() => `/api/races/${props.year}/${props.round}/simulate`, {
  query,
  server: false,
  key: `simulate:${props.year}:${props.round}`,
})
// Keep the last good answer on screen while a new plan is computed or when a plan is not allowed.
const sim = ref<Simulation | null>(null)
watch(fetched, (v) => {
  if (!v) return
  sim.value = v
  if (!edited.value) {
    driver.value = v.driver
    stops.value = v.actual.slice(0, -1).map((s) => s.to_lap)
    compounds.value = v.actual.map((s) => s.compound)
  }
})
const problem = computed(() => (error.value?.data as { detail?: string } | undefined)?.detail ?? (error.value ? 'This plan could not be simulated.' : ''))

function pickDriver(id: string) {
  edited.value = false
  driver.value = id
}
function reset() {
  edited.value = false
  query.value = { ...query.value, driver: driver.value }
  if (sim.value) {
    stops.value = sim.value.actual.slice(0, -1).map((s) => s.to_lap)
    compounds.value = sim.value.actual.map((s) => s.compound)
  }
}
function edit(fn: () => void) {
  fn()
  edited.value = true
}
const lastLap = computed(() => sim.value?.last_lap ?? 0)
function setStop(i: number, lap: number) {
  const low = i ? stops.value[i - 1]! + 1 : 1
  const high = i + 1 < stops.value.length ? stops.value[i + 1]! - 1 : lastLap.value - 1
  edit(() => (stops.value[i] = Math.min(high, Math.max(low, Math.round(lap) || low))))
}
function addStop() {
  const bounds = [0, ...stops.value, lastLap.value]
  // Split the longest stint in two.
  let k = 0
  for (let i = 1; i < bounds.length - 1; i++) if (bounds[i + 1]! - bounds[i]! > bounds[k + 1]! - bounds[k]!) k = i
  const lap = Math.floor((bounds[k]! + bounds[k + 1]!) / 2)
  if (lap <= bounds[k]! || lap >= lastLap.value) return
  edit(() => {
    stops.value.splice(k, 0, lap)
    compounds.value.splice(k + 1, 0, compounds.value[k] ?? 'HARD')
  })
}
function removeStop(i: number) {
  edit(() => {
    stops.value.splice(i, 1)
    compounds.value.splice(i + 1, 1)
  })
}
function useBest() {
  if (sim.value) edit(() => (stops.value = [...sim.value!.best.stops]))
}

const available = computed(() => Object.keys(sim.value?.model.compounds ?? {}).map((c) => ({ value: c, label: compound(c).label })))
const stints = computed(() => {
  const bounds = [0, ...stops.value, lastLap.value]
  return compounds.value.map((c, i) => ({ compound: c, from: bounds[i]! + 1, to: bounds[i + 1]! }))
})
const driverOptions = computed(() =>
  (sim.value?.drivers ?? []).map((id) => {
    const d = props.drivers.find((x) => x.driver_id === id)
    return { value: id, label: d?.name ?? id, sub: d?.constructor, swatch: d ? teamColor(d.constructor_id) : undefined }
  }),
)

const change = computed(() => sim.value?.time_change_s ?? 0)
const changeText = computed(() => (Math.abs(change.value) < 0.05 ? 'Same' : `${change.value > 0 ? '+' : '−'}${Math.abs(change.value).toFixed(1)} s`))
const bestGain = computed(() => sim.value?.best.time_change_s ?? 0)
const bestIsCurrent = computed(() => !!sim.value && sim.value.best.stops.join(',') === stops.value.join(','))

const strip = useChartOption<EChartsOption>(() => {
  const s = sim.value
  if (!s) return {}
  const row = (id: string, name: string, plan: PlanStint[]): StrategyDriver => ({
    driver_id: id,
    abbreviation: name,
    name,
    constructor_id: '',
    constructor: '',
    position: null,
    position_text: '',
    laps: s.last_lap,
    stints: plan.map((p, i) => ({
      stint: i + 1,
      compound: p.compound,
      from_lap: p.from_lap,
      to_lap: p.to_lap,
      laps: p.to_lap - p.from_lap + 1,
      tyre_age_at_start: p.age_start,
    })),
  })
  const opt = strategyOption([row('real', 'Real', s.actual), row('sim', 'What if', s.plan)], s.last_lap, s.periods)
  return { ...opt, grid: { left: 8, right: 16, top: 8, bottom: 28, containLabel: true } }
})

const positionChart = useChartOption<EChartsOption>(() => {
  const s = sim.value
  if (!s) return {}
  const real = cssVar('--muted')
  const what = seriesColor(1)
  return {
    animation: false,
    legend: { top: 0, left: 0, data: ['Real race', 'What if'] },
    grid: { left: 8, right: 16, top: 36, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (p: unknown) => {
        const l = s.laps[(p as { dataIndex: number }[])[0]!.dataIndex]!
        const d = l.delta_s
        const t = Math.abs(d) < 0.05 ? 'level with the real race' : `${Math.abs(d).toFixed(1)} s ${d < 0 ? 'ahead of' : 'behind'} the real race`
        return `<b>Lap ${l.lap}</b><br>Real: P${l.real ?? '–'}<br>What if: P${l.simulated ?? '–'}<br><span style="opacity:.75">${t}</span>`
      },
    },
    xAxis: { type: 'value', name: 'Lap', min: 1, max: s.last_lap, minInterval: 1 },
    yAxis: { type: 'value', inverse: true, min: 1, minInterval: 1, axisLabel: { formatter: (v: number) => `P${v}` } },
    series: [
      {
        name: 'Real race',
        type: 'line',
        step: 'middle',
        data: s.laps.map((l) => [l.lap, l.real]),
        color: real,
        symbol: 'none',
        lineStyle: { width: 2, type: [5, 3] },
        markArea: neutralBands(s.periods),
      },
      { name: 'What if', type: 'line', step: 'middle', data: s.laps.map((l) => [l.lap, l.simulated]), color: what, symbol: 'none', lineStyle: { width: 2 } },
    ] as SeriesOption[],
  }
})

const modelRows = computed(() => {
  const m = sim.value?.model
  if (!m) return []
  return Object.entries(m.compounds).map(([c, p]) => ({ compound: c, ...p, reference: c === m.reference }))
})
</script>

<template>
  <Panel title="What if? Strategy simulator" note="Change one driver's stop laps or tyres. Everyone else keeps their real race; the driver's lap times change by what the tyre model says the new plan was worth.">
    <template #actions>
      <UiSelect v-if="driverOptions.length" :model-value="driver" label="Driver" :options="driverOptions" searchable @update:model-value="pickDriver" />
    </template>

    <div v-if="!sim && status !== 'error'" class="skeleton" style="height: 320px" />
    <EmptyState v-else-if="!sim" title="No simulation for this race" :text="problem" />
    <div v-else class="stack">
      <div class="planner" :class="{ dim: status === 'pending' }">
        <template v-for="(st, i) in stints" :key="i">
          <div class="stint">
            <span class="tyre" :style="{ background: compound(st.compound).color, color: compound(st.compound).ink }">{{ compound(st.compound).short }}</span>
            <div class="stint-body">
              <UiChoice
                :model-value="st.compound"
                :label="`Tyres for stint ${i + 1}`"
                :options="available"
                collapse="always"
                @update:model-value="(v: string) => edit(() => (compounds[i] = v))"
              />
              <span class="small muted">Laps {{ st.from }}–{{ st.to }} · {{ st.to - st.from + 1 }} laps</span>
            </div>
          </div>
          <div v-if="i < stops.length" class="stop">
            <span class="small">Pit after lap</span>
            <div class="stepper">
              <button class="btn icon" type="button" :aria-label="`Stop ${i + 1} one lap earlier`" @click="setStop(i, stops[i]! - 1)">−</button>
              <input class="input num" type="number" :value="stops[i]" :min="1" :max="lastLap - 1" :aria-label="`Lap of stop ${i + 1}`" @change="setStop(i, Number(($event.target as HTMLInputElement).value))" />
              <button class="btn icon" type="button" :aria-label="`Stop ${i + 1} one lap later`" @click="setStop(i, stops[i]! + 1)">+</button>
            </div>
            <button class="btn ghost small" type="button" @click="removeStop(i)">Remove stop</button>
          </div>
        </template>
        <div class="row wrap actions">
          <button class="btn" type="button" :disabled="stops.length >= 5" @click="addStop">Add a stop</button>
          <button class="btn" type="button" :disabled="!edited" @click="reset">Back to the real plan</button>
          <button v-if="!bestIsCurrent && stops.length" class="btn" type="button" @click="useBest">
            Best stop laps for these tyres <span class="muted">({{ sim.best.stops.join(', ') }})</span>
          </button>
        </div>
      </div>

      <p v-if="problem" class="note bad" role="alert">{{ problem }}</p>
      <p v-for="w in sim.warnings" :key="w" class="note warn">{{ w }}</p>

      <Tiles>
        <StatTile label="Race time" :value="changeText" :hint="change < -0.05 ? 'Faster than the real race' : change > 0.05 ? 'Slower than the real race' : 'Same as the real plan'" />
        <StatTile
          label="Finishing position"
          :value="sim.position.simulated ? `P${sim.position.simulated}` : '–'"
          :hint="sim.position.real ? (sim.position.real === sim.position.simulated ? 'No change' : `P${sim.position.real} in the real race`) : ''"
        />
        <StatTile label="Car ahead" :value="sim.ahead ? short(sim.ahead.driver_id) : '–'" :hint="sim.ahead ? `${sim.ahead.gap_s.toFixed(1)} s ahead at the flag` : 'Nobody: leads the race'" />
        <StatTile label="Car behind" :value="sim.behind ? short(sim.behind.driver_id) : '–'" :hint="sim.behind ? `${sim.behind.gap_s.toFixed(1)} s behind at the flag` : 'Nobody on the same lap'" />
      </Tiles>
      <p v-if="Math.abs(change) >= 0.05 && sim.ahead && sim.ahead.gap_s < 1" class="note">Within a second of {{ short(sim.ahead.driver_id) }}: close enough that traffic and tyre warm-up, which the model leaves out, would decide it.</p>

      <div class="grid-12">
        <div class="span-12">
          <Chart :option="strip" :height="110" label="Real and simulated tyre plan" />
        </div>
        <div class="span-12">
          <Chart :option="positionChart" :height="280" :compact-height="240" label="Position by lap in the real race and in the simulated one" />
        </div>
      </div>

      <details class="method small">
        <summary><b>The tyre model for this race</b> <span class="muted">· fitted on {{ sim.model.laps }} green-flag laps, typical error {{ sim.model.rmse_s.toFixed(2) }} s</span></summary>
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th>Tyre</th><th class="r">On new tyres</th><th class="r">Wear per lap</th><th class="r hide-sm">Laps</th></tr></thead>
            <tbody>
              <tr v-for="r in modelRows" :key="r.compound">
                <td class="nowrap"><span class="swatch" :style="{ background: compound(r.compound).color }" /> {{ compound(r.compound).label }}</td>
                <td class="r num">{{ r.reference ? 'reference' : `${r.offset_s < 0 ? '' : '+'}${r.offset_s.toFixed(2)} s` }}</td>
                <td class="r num">{{ r.wear_s_per_lap.toFixed(3) }} s</td>
                <td class="r hide-sm num">{{ r.laps }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="prose">
          <p>Lap time, with the weight of fuel taken out, is modelled as the driver's pace plus a tyre offset plus wear for every lap the tyres have done, plus a trend for the track getting faster over the race. The tyre numbers are shared by the whole field and fitted on clean, green-flag laps. A softer tyre is never allowed to wear more slowly than a harder one, and wear is never negative.</p>
          <p>
            A stop costs {{ sim.pit_loss_s }} s<template v-if="sim.pit_loss_measured">, the median green-flag stop in this race</template><template v-else>, a typical figure (too few green-flag stops here to measure)</template>,
            {{ Math.round((sim.method.pit_factor.sc ?? 0.5) * 100) }}% of that under a safety car, {{ Math.round((sim.method.pit_factor.vsc ?? 0.65) * 100) }}% under a virtual safety car and nothing under a red flag. Laps behind the safety car cost the same on any tyre.
          </p>
          <p><b>Not modelled:</b> traffic after a stop, tyre warm-up, rivals reacting, and a track that changes with the weather.<template v-if="sim.model.left_out.length"> Tyres used in other conditions ({{ sim.model.left_out.map((c) => compound(c).label.toLowerCase()).join(', ') }}) are left out.</template></p>
        </div>
      </details>
    </div>
  </Panel>
</template>

<style scoped>
.planner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: opacity 0.15s;
}
.dim {
  opacity: 0.6;
}
.stint {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-2);
}
.stint-body {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  min-width: 0;
}
.tyre {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 750;
  border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--border-strong);
}
.stop {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-left: 52px;
}
.stepper {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.stepper .input {
  width: 64px;
  text-align: center;
}
.actions {
  gap: 8px;
  margin-top: 4px;
}
.note {
  margin: 0;
  padding: 8px 12px;
  border-radius: 10px;
  background: var(--surface-2);
  font-size: 13px;
}
.note.warn {
  border-left: 3px solid var(--warning);
}
.note.bad {
  border-left: 3px solid var(--bad);
}
.method summary {
  cursor: pointer;
  padding: 4px 0;
}
.method .prose {
  margin-top: 10px;
}
.method .prose p + p {
  margin-top: 8px;
}
@media (max-width: 640px) {
  .stop {
    padding-left: 0;
  }
}
</style>
