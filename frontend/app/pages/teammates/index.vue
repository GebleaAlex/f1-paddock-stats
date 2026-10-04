<script setup lang="ts">
interface Pairing {
  driver_a: string
  name_a: string
  driver_b: string
  name_b: string
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
  constructors: string[]
}

const era = useQueryState('era', 'all')
const minRaces = useQueryNumber('min', 15)
const order = useQueryState('order', 'lopsided')
const ERAS = [
  { id: 'all', label: 'All years', from: 1950, to: 2100 },
  { id: 'current', label: 'Last 5 years', from: new Date().getFullYear() - 4, to: 2100 },
  ...[2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950].map((d) => ({ id: String(d), label: `${d}s`, from: d, to: d + 9 })),
]
const ERA_OPTIONS = ERAS.map((e) => ({ value: e.id, label: e.label }))
const MIN_OPTIONS = [5, 15, 30, 50].map((m) => ({ value: String(m), label: `${m}+ races` }))
const ORDER_OPTIONS = [
  { value: 'lopsided', label: 'Most one-sided' },
  { value: 'closest', label: 'Closest' },
  { value: 'gap', label: 'Biggest gap' },
  { value: 'races', label: 'Most races' },
]
const minModel = computed({ get: () => String(minRaces.value), set: (v: string) => (minRaces.value = Number(v)) })
const window_ = computed(() => ERAS.find((e) => e.id === era.value) ?? ERAS[0]!)
const { data: pairs } = await useApi<Pairing[]>(() => `/teammates?from=${window_.value.from}&to=${window_.value.to}&min_races=${minRaces.value}`)

usePageMeta({ title: 'Teammate head-to-heads', description: 'Every Formula 1 teammate pairing since 1950, ranked by how one-sided the qualifying and race duels were.' })

// Each pairing is shown from the side of the driver who won the qualifying duel.
const rows = computed(() => {
  const list = (pairs.value ?? []).map((p) => {
    const flip = p.quali_lost > p.quali_won
    const o = flip
      ? {
          a: p.driver_b, nameA: p.name_b, b: p.driver_a, nameB: p.name_a,
          qw: p.quali_lost, ql: p.quali_won, rw: p.race_lost, rl: p.race_won,
          pa: p.points_mate, pb: p.points_me, gap: p.median_gap_pct == null ? null : -p.median_gap_pct,
        }
      : {
          a: p.driver_a, nameA: p.name_a, b: p.driver_b, nameB: p.name_b,
          qw: p.quali_won, ql: p.quali_lost, rw: p.race_won, rl: p.race_lost,
          pa: p.points_me, pb: p.points_mate, gap: p.median_gap_pct,
        }
    const qShare = o.qw + o.ql ? o.qw / (o.qw + o.ql) : 0.5
    return { ...p, ...o, qShare }
  })
  const sorters: Record<string, (x: (typeof list)[number], y: (typeof list)[number]) => number> = {
    lopsided: (x, y) => y.qShare - x.qShare || y.races - x.races,
    closest: (x, y) => Math.abs(x.qShare - 0.5) - Math.abs(y.qShare - 0.5) || y.races - x.races,
    gap: (x, y) => (x.gap ?? 0) - (y.gap ?? 0),
    races: (x, y) => y.races - x.races,
  }
  return list.sort(sorters[order.value] ?? sorters.lopsided)
})
const limit = ref(100)
watch([era, minRaces, order], () => (limit.value = 100))
</script>

<template>
  <div>
    <PageHeader
      title="Teammate head-to-heads"
      sub="The only fair fight in Formula 1 is against the driver in the same car. Every pairing is shown from the side of the driver who won the qualifying duel."
    />
    <div class="filters">
      <UiSelect v-model="era" label="Years" :options="ERA_OPTIONS" />
      <UiSelect v-model="minModel" label="Together" :options="MIN_OPTIONS" />
      <UiChoice v-model="order" label="Order" :options="ORDER_OPTIONS" collapse="md" />
      <span class="small muted count">{{ rows.length }} pairing{{ rows.length === 1 ? '' : 's' }}</span>
    </div>
    <section class="panel flush">
      <div class="table-scroll">
        <table class="data">
          <thead>
            <tr>
              <th>Stronger qualifier</th><th class="hide-sm">Teammate</th><th class="hide-md">Team</th><th class="hide-md">Years</th><th class="r hide-sm">Races</th>
              <th class="c">Qualifying</th><th class="c hide-sm">Race</th><th class="r hide-md">Points</th><th class="r hide-sm">Median gap</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows.slice(0, limit)" :key="r.driver_a + r.driver_b">
              <td>
                <NuxtLink :to="`/teammates/${r.a}/${r.b}`" class="pair"><b>{{ r.nameA }}</b><span class="only-sm vs"> vs {{ r.nameB }}</span></NuxtLink>
                <span class="sub-line only-md">{{ r.constructors.join(', ') }} · {{ years(r.first_year, r.last_year) }}<span class="only-sm dot">{{ r.races }} races</span></span>
              </td>
              <td class="nowrap hide-sm"><NuxtLink :to="`/teammates/${r.a}/${r.b}`">{{ r.nameB }}</NuxtLink></td>
              <td class="small ink-2 hide-md">{{ r.constructors.join(', ') }}</td>
              <td class="small num nowrap hide-md">{{ years(r.first_year, r.last_year) }}</td>
              <td class="r hide-sm">{{ r.races }}</td>
              <td><DuelBar :won="r.qw" :lost="r.ql" /></td>
              <td class="hide-sm"><DuelBar :won="r.rw" :lost="r.rl" /></td>
              <td class="r small nowrap hide-md">{{ points(r.pa) }}–{{ points(r.pb) }}</td>
              <td class="r nowrap hide-sm">{{ pct(r.gap) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-if="!rows.length" title="No pairings with that many races" text="Lower the minimum number of races or pick another era." />
      </div>
    </section>
    <div v-if="rows.length > limit" class="more"><button class="btn" @click="limit += 200">Show more</button></div>
  </div>
</template>

<style scoped>
.count {
  margin-left: auto;
}
.pair .vs {
  font-weight: 500;
}
@media (max-width: 640px) {
  .count {
    display: none;
  }
}
.more {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
