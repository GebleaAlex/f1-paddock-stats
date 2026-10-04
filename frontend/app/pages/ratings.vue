<script setup lang="ts">
// Cross-era driver rating from chained teammate comparisons, with its 90% interval drawn as a bar.
interface Rating {
  rank: number
  driver_id: string
  name: string
  skill: number
  low: number
  high: number
  comparisons: number
  teammates: number
  first_year: number | null
  last_year: number | null
  championships: number
  wins: number
}

const kind = useQueryState('kind', 'drivers')
usePageMeta({
  title: () => (kind.value === 'cars' ? 'Car rating across eras' : 'Driver rating across eras'),
  description: () =>
    kind.value === 'cars'
      ? 'How fast every Formula 1 car was against its rivals since 1950, from qualifying pace with the drivers taken out.'
      : 'An open rating of every Formula 1 driver since 1950, built only from comparisons with their teammates, with the uncertainty shown.',
  stats: () => (kind.value === 'cars' ? [] : (data.value?.rows ?? []).slice(0, 4).map((r) => [`${r.rank}.`, r.name])),
})

const model = useQueryState('model', 'combined')
const minCmp = useQueryState('min', '40')
const era = useQueryState('era', 'all')
const ERAS = [
  { value: 'all', label: 'All eras', from: 1950, to: 2100 },
  { value: 'modern', label: 'Racing since 2014', from: 2014, to: 2100 },
  ...[2010, 2000, 1990, 1980, 1970, 1960, 1950].map((d) => ({ value: String(d), label: `Raced in the ${d}s`, from: d, to: d + 9 })),
]
const MODELS = [
  { value: 'combined', label: 'Qualifying and races', sub: 'Both, on one scale' },
  { value: 'qualifying', label: 'Qualifying pace', sub: 'Gap to the teammate in qualifying' },
  { value: 'race', label: 'Race results', sub: 'Places ahead of the teammate, both finished' },
]
const MINS = ['20', '40', '80', '150'].map((v) => ({ value: v, label: `${v}+ comparisons` }))
const e = computed(() => ERAS.find((x) => x.value === era.value) ?? ERAS[0]!)
const { data, pending } = await useApi<{ rows: Rating[]; description: string }>(
  () => `/ratings?model=${model.value}&min_comparisons=${minCmp.value}&from=${e.value.from}&to=${e.value.to}&limit=100`,
)
const scale = computed(() => {
  const rows = data.value?.rows ?? []
  const lo = Math.min(0, ...rows.map((r) => r.low))
  const hi = Math.max(...rows.map((r) => r.high), 1)
  return { lo, hi, span: hi - lo || 1 }
})
const at = (v: number) => `${((v - scale.value.lo) / scale.value.span) * 100}%`
</script>

<template>
  <div>
    <PageHeader
      :title="kind === 'cars' ? 'Car rating across eras' : 'Driver rating across eras'"
      :sub="
        kind === 'cars'
          ? 'Which cars were really the fastest? Qualifying pace with the drivers taken out, season by season since 1950.'
          : 'Who was fastest? Teammates are the only fair comparison, so this rating uses nothing else: every teammate duel since 1950, chained across careers.'
      "
    />
    <Tabs v-model="kind" :tabs="[{ id: 'drivers', label: 'Drivers' }, { id: 'cars', label: 'Cars and teams' }]" label="Rating" class="kinds" />
    <CarRatings v-if="kind === 'cars'" />
    <template v-else>
    <div class="filters">
      <UiChoice v-model="model" label="Based on" :options="MODELS" />
      <UiSelect v-model="era" label="Show" :options="ERAS" />
      <UiSelect v-model="minCmp" label="At least" :options="MINS" />
    </div>

    <div class="grid-12">
      <Panel class="span-8" :title="MODELS.find((m) => m.value === model)?.label ?? ''" :note="`The dot is the rating, the bar its 90% range. ${data?.rows.length ?? 0} drivers shown.`" flush>
        <ol class="board" :class="{ dim: pending }">
          <li v-for="r in data?.rows ?? []" :key="r.driver_id">
            <span class="rank num">{{ r.rank }}</span>
            <div class="who">
              <NuxtLink :to="`/drivers/${r.driver_id}`"><b>{{ r.name }}</b></NuxtLink>
              <span class="sub-line">{{ years(r.first_year, r.last_year) }} · {{ r.teammates }} teammates · {{ r.comparisons }} comparisons<template v-if="r.championships"> · {{ r.championships }}× champion</template></span>
            </div>
            <div class="scale" role="img" :aria-label="`Rating ${r.skill.toFixed(2)}, range ${r.low.toFixed(2)} to ${r.high.toFixed(2)}`">
              <span class="zero" :style="{ left: at(0) }" />
              <span class="range" :style="{ left: at(r.low), width: `calc(${at(r.high)} - ${at(r.low)})` }" />
              <span class="marker" :style="{ left: at(r.skill) }" />
            </div>
            <span class="value num">{{ r.skill > 0 ? '+' : '' }}{{ r.skill.toFixed(2) }}</span>
          </li>
        </ol>
      </Panel>
      <Panel class="span-4 method" title="How it works">
        <div class="prose small">
          <p>Every race in which two teammates both set a qualifying time, or both finished, says how much faster one was than the other in the same car.</p>
          <p>Putting all of them together links drivers across eras through shared teammates: Prost raced Senna, Senna raced Berger, Berger raced Alesi, and so on. A least-squares fit finds the ratings that best explain every duel at once.</p>
          <p>Each season's gaps are measured against the typical teammate gap of that season, so a 1950s spread and today's tight field count the same. A rating of +1 means beating the average driver by one typical teammate gap.</p>
          <p><b>Limits.</b> A chain is only as strong as its weakest link. Drivers with one or two teammates are rated mostly against them, which the wider range shows. Team orders, age, injuries and car development are not modelled. Teammates must have been entered by the same team, and the Indianapolis 500 is left out.</p>
          <p class="muted">The code is open: <code>backend/paddock/rating.py</code>.</p>
        </div>
      </Panel>
    </div>
    </template>
  </div>
</template>

<style scoped>
.kinds {
  margin-bottom: 16px;
}
.board {
  list-style: none;
  margin: 0;
  padding: 0 0 8px;
}
.board li {
  display: grid;
  grid-template-columns: 36px minmax(0, 1.3fr) minmax(0, 2fr) 56px;
  gap: 12px;
  align-items: center;
  padding: 9px var(--pad);
  border-bottom: 1px solid var(--grid);
}
.board li:last-child {
  border-bottom: 0;
}
.rank {
  color: var(--muted);
  text-align: right;
  font-weight: 600;
}
.who {
  min-width: 0;
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
.dim {
  opacity: 0.55;
}
.method .prose p + p {
  margin-top: 10px;
}
@media (max-width: 640px) {
  .board li {
    grid-template-columns: 28px minmax(0, 1fr) 52px;
  }
  .scale {
    grid-column: 2 / -1;
    grid-row: 2;
  }
}
</style>
