<script setup lang="ts">
import type { DriverRow } from '~/utils/types'

const { data: drivers } = await useApi<DriverRow[]>('/drivers')
usePageMeta({ title: 'Drivers', description: 'Every Formula 1 driver since 1950 with career totals: starts, wins, podiums, poles and titles.' })

const q = useQueryState('q', '')
const era = useQueryState('era', 'all')
const only = useQueryState('only', 'all')
const limit = ref(100)

const ERAS = [
  { value: 'all', label: 'All decades' },
  ...[2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950].map((d) => ({ value: String(d), label: `${d}s` })),
]
const ONLY = [
  { value: 'all', label: 'Everyone' },
  { value: 'starters', label: 'Started a race' },
  { value: 'winners', label: 'Race winners' },
  { value: 'champions', label: 'Champions' },
]

const strip = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
const filtered = computed(() => {
  const term = strip(q.value.trim())
  const decade = era.value === 'all' ? null : Number(era.value)
  return (drivers.value ?? []).filter((d) => {
    if (term && !strip(d.name).includes(term)) return false
    if (decade && !(d.first_year && d.last_year && d.first_year <= decade + 9 && d.last_year >= decade)) return false
    if (only.value === 'winners' && !d.wins) return false
    if (only.value === 'champions' && !d.championships) return false
    if (only.value === 'starters' && !d.starts) return false
    return true
  })
})
const { sorted, by, aria, key: sortKey } = useSorted(filtered, '-wins')
const rows = computed(() => sorted.value.slice(0, limit.value))
watch([q, era, only], () => (limit.value = 100))

const COLS = [
  { key: 'starts', label: 'Starts' },
  { key: 'wins', label: 'Wins' },
  { key: 'podiums', label: 'Podiums' },
  { key: 'poles', label: 'Poles' },
  { key: 'championships', label: 'Titles' },
  { key: 'points', label: 'Points' },
] as const
type ColKey = (typeof COLS)[number]['key']

// Phones show one number column: whatever the list is sorted by (wins by default), chosen from a dropdown.
const sortModel = useQueryState('sort', '-wins')
const SORT_OPTIONS = [...COLS.map((c) => ({ value: `-${c.key}`, label: `Most ${c.label.toLowerCase()}` })), { value: 'name', label: 'Name A–Z' }]
const mobileCol = computed<ColKey>(() => (COLS.some((c) => c.key === sortKey.value) ? (sortKey.value as ColKey) : 'wins'))
const mobileLabel = computed(() => COLS.find((c) => c.key === mobileCol.value)!.label)
const fmt = (d: DriverRow, k: ColKey) => (k === 'points' ? (d.points ? points(d.points) : '') : d[k] || '')
</script>

<template>
  <div>
    <PageHeader title="Drivers" :sub="`${drivers?.length ?? ''} drivers have entered a world championship race since 1950.`">
      <NuxtLink class="btn" to="/compare">Compare drivers</NuxtLink>
    </PageHeader>
    <div class="filters">
      <input v-model="q" class="input search" type="search" placeholder="Filter by name" aria-label="Filter drivers by name">
      <UiSelect v-model="era" label="Decade" :options="ERAS" />
      <UiChoice v-model="only" label="Show" :options="ONLY" collapse="md" />
      <UiSelect v-model="sortModel" class="only-sm" label="Sort" :options="SORT_OPTIONS" />
      <span class="small muted count">{{ filtered.length }} driver{{ filtered.length === 1 ? '' : 's' }}</span>
    </div>
    <section class="panel flush">
      <div class="table-scroll">
        <table class="data">
          <thead>
            <tr>
              <th class="sortable" :aria-sort="aria('name')" @click="by('name', false)">Driver</th>
              <th class="sortable hide-md" :aria-sort="aria('nationality')" @click="by('nationality', false)">Nationality</th>
              <th class="sortable hide-sm" :aria-sort="aria('first_year')" @click="by('first_year', false)">Years</th>
              <th v-for="c in COLS" :key="c.key" class="r sortable hide-sm" :aria-sort="aria(c.key)" @click="by(c.key)">{{ c.label }}</th>
              <th class="r only-sm-cell">{{ mobileLabel }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in rows" :key="d.id">
              <td>
                <NuxtLink :to="`/drivers/${d.id}`"><b>{{ d.name }}</b></NuxtLink>
                <span class="sub-line only-md">{{ d.nationality }}<span class="only-sm dot">{{ years(d.first_year, d.last_year) }}</span></span>
              </td>
              <td class="small ink-2 hide-md">{{ d.nationality }}</td>
              <td class="small num nowrap hide-sm">{{ years(d.first_year, d.last_year) }}</td>
              <td v-for="c in COLS" :key="c.key" class="r hide-sm" :class="{ 'strong-cell': c.key === 'wins' || c.key === 'championships' }">{{ fmt(d, c.key) }}</td>
              <td class="r only-sm-cell strong-cell">{{ fmt(d, mobileCol) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-if="!filtered.length" title="No driver matches these filters" text="Try another decade or clear the name filter." />
      </div>
    </section>
    <div v-if="filtered.length > limit" class="more">
      <button class="btn" @click="limit += 200">Show more ({{ filtered.length - limit }} left)</button>
    </div>
  </div>
</template>

<style scoped>
.search {
  width: 220px;
}
.count {
  margin-left: auto;
}
.more {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
@media (max-width: 640px) {
  .search {
    width: 100%;
  }
  .count {
    display: none;
  }
}
</style>
