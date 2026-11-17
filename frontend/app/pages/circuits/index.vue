<script setup lang="ts">
interface CircuitRow {
  id: string
  name: string
  type: string
  place_name: string
  country: string
  races: number
  first_year: number | null
  last_year: number | null
  length: number | null
  turns: number | null
  layout_path: string | null
}

const { data: circuits } = await useApi<CircuitRow[]>('/circuits')
usePageMeta({ title: 'Circuits', description: 'Every circuit that has hosted a Formula 1 world championship race, with layouts and winners.' })

const only = useQueryState('only', 'all')
const q = useQueryState('q', '')
// Math.max() of nothing is -Infinity, which would end up in the "On the ... calendar" label.
const latest = computed(() => Math.max(0, ...(circuits.value ?? []).map((c) => c.last_year ?? 0)))
// The name filter also matches the town and the country, and applies to both views.
const matches = (c: { name: string; place_name: string; last_year: number | null; country?: string }) => {
  if (only.value === 'current' && c.last_year !== latest.value) return false
  const term = fold(q.value.trim())
  return !term || fold(`${c.name} ${c.place_name} ${c.country ?? ''}`).includes(term)
}
const shown = computed(() => (circuits.value ?? []).filter(matches))
const TYPES: Record<string, string> = { RACE: 'Race circuit', STREET: 'Street circuit', ROAD: 'Road course' }

interface ConditionsRow {
  circuit_id: string
  name: string
  place_name: string
  races: number
  first_year: number
  last_year: number
  safety_car_races: number
  safety_cars: number
  virtual_safety_cars: number
  red_flag_races: number
  wet_races: number
  rain_races: number
  neutralised_pct: number | null
  safety_car_chance: number
  safety_cars_per_race: number
}
const view = useQueryState('view', 'layouts')
const { data: conditions, execute: loadConditions } = useFetch<{ circuits: ConditionsRow[]; totals: { races: number; safety_car_chance: number | null } }>(
  '/api/conditions',
  { server: false, immediate: false, key: 'conditions' },
)
watch(view, (v) => import.meta.client && v === 'conditions' && !conditions.value && loadConditions(), { immediate: true })
onMounted(() => view.value === 'conditions' && !conditions.value && loadConditions())
const countryOf = computed(() => new Map((circuits.value ?? []).map((c) => [c.id, c.country])))
const rows = computed(() => (conditions.value?.circuits ?? []).filter((c) => matches({ ...c, country: countryOf.value.get(c.circuit_id) })))
const { sorted, th } = useSorted(rows, '-safety_car_chance')
</script>

<template>
  <div>
    <PageHeader title="Circuits" :sub="`${circuits?.length ?? ''} circuits have hosted a world championship race. Layouts from f1db.`">
      <UiChoice v-model="only" label="Show" :options="[{ value: 'all', label: 'All circuits' }, { value: 'current', label: latest ? `On the ${latest} calendar` : 'On the calendar' }]" />
    </PageHeader>
    <Tabs v-model="view" :tabs="[{ id: 'layouts', label: 'Layouts' }, { id: 'conditions', label: 'Safety cars and rain' }]" label="Circuit views" class="views" />
    <div class="filters">
      <input v-model="q" class="input search" type="search" placeholder="Filter by name, town or country" aria-label="Filter circuits by name, town or country">
      <span v-if="view !== 'conditions'" class="small muted count">{{ shown.length }} circuit{{ shown.length === 1 ? '' : 's' }}</span>
    </div>
    <Panel
      v-if="view === 'conditions'"
      title="Where the safety car comes out"
      :note="conditions ? `Circuits with at least three races in the timing data (2018 on). Across all ${conditions.totals.races} races, ${Math.round((conditions.totals.safety_car_chance ?? 0) * 100)}% had a safety car.` : 'From the timing data, 2018 on.'"
      flush
    >
      <div v-if="!conditions" class="skeleton" style="height: 360px; margin: 0 var(--pad) var(--pad)" />
      <EmptyState v-else-if="!conditions.circuits.length" title="Not enough timing data yet" text="Circuits appear here once three of their races have timing data, loaded with paddock timing." />
      <EmptyState v-else-if="!sorted.length" title="No circuit matches" text="Clear the filter or show all circuits. Only circuits with three races since 2018 are listed here." />
      <div v-else class="table-scroll">
        <table class="data">
          <thead>
            <tr>
              <th>Circuit</th>
              <th class="r sortable" v-bind="th('races')">Races</th>
              <th class="r sortable" v-bind="th('safety_car_chance')">Safety car</th>
              <th class="r sortable hide-sm" v-bind="th('safety_cars_per_race')">Per race</th>
              <th class="r sortable hide-md" v-bind="th('virtual_safety_cars')">Virtual</th>
              <th class="r sortable hide-md" v-bind="th('red_flag_races')">Red flags</th>
              <th class="r sortable" v-bind="th('wet_races')">Wet</th>
              <th class="r sortable hide-sm" v-bind="th('neutralised_pct')">Laps neutralised</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in sorted" :key="c.circuit_id">
              <td><NuxtLink :to="`/circuits/${c.circuit_id}`"><b>{{ c.name }}</b></NuxtLink><span class="sub-line">{{ c.place_name }} · {{ years(c.first_year, c.last_year) }}</span></td>
              <td class="r num">{{ c.races }}</td>
              <td class="r num nowrap"><b>{{ Math.round(c.safety_car_chance * 100) }}%</b> <span class="muted tiny hide-sm">{{ c.safety_car_races }}/{{ c.races }}</span></td>
              <td class="r num hide-sm">{{ c.safety_cars_per_race.toFixed(1) }}</td>
              <td class="r num hide-md">{{ c.virtual_safety_cars }}</td>
              <td class="r num hide-md">{{ c.red_flag_races || '' }}</td>
              <td class="r num">{{ c.wet_races || '' }}</td>
              <td class="r num hide-sm">{{ c.neutralised_pct != null ? `${c.neutralised_pct}%` : '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
    <div v-else-if="!shown.length" class="panel"><EmptyState title="No circuit matches" text="Clear the filter or show all circuits." /></div>
    <div v-else class="cards">
      <NuxtLink v-for="c in shown" :key="c.id" :to="`/circuits/${c.id}`" class="card card-link">
        <svg v-if="c.layout_path" viewBox="0 0 500 500" class="layout" aria-hidden="true"><path :d="c.layout_path" /></svg>
        <div class="grow">
          <b>{{ c.name }}</b>
          <div class="small ink-2">{{ c.place_name }}, {{ c.country }}</div>
          <div class="tiny muted">{{ c.races }} race{{ c.races === 1 ? '' : 's' }} · {{ years(c.first_year, c.last_year) }} · {{ TYPES[c.type] ?? c.type }}</div>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.views {
  margin-bottom: 16px;
}
.search {
  width: 280px;
}
.count {
  margin-left: auto;
}
@media (max-width: 640px) {
  .search {
    width: 100%;
  }
  .count {
    display: none;
  }
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: 10px;
}
.card {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 12px 14px;
}
.layout {
  width: 64px;
  height: 64px;
  flex: none;
}
.layout path {
  fill: none;
  stroke: var(--ink);
  stroke-width: 18;
  stroke-linejoin: round;
}
</style>
