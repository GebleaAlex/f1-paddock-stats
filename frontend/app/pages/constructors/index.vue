<script setup lang="ts">
interface ConstructorRow {
  id: string
  name: string
  country: string | null
  starts: number
  wins: number
  podiums: number
  poles: number
  one_twos: number
  championships: number
  points: number
  first_year: number | null
  last_year: number | null
}

const { data: teams } = await useApi<ConstructorRow[]>('/constructors')
usePageMeta({ title: 'Teams', description: 'Every Formula 1 constructor since 1950 with wins, poles, one-twos and titles.' })

const q = useQueryState('q', '')
const only = useQueryState('only', 'winners')
const filtered = computed(() => {
  const term = q.value.trim().toLowerCase()
  return (teams.value ?? []).filter((t) => {
    if (term && !t.name.toLowerCase().includes(term)) return false
    if (only.value === 'winners' && !t.wins) return false
    if (only.value === 'current' && t.last_year !== Math.max(...(teams.value ?? []).map((x) => x.last_year ?? 0))) return false
    return true
  })
})
const { sorted, by, aria } = useSorted(filtered, '-wins')
const rows = computed(() => sorted.value)
const ONLY = [
  { value: 'current', label: 'Current' },
  { value: 'winners', label: 'Race winners' },
  { value: 'all', label: 'All teams' },
]
</script>

<template>
  <div>
    <PageHeader title="Teams" :sub="`${teams?.length ?? ''} constructors have raced in the world championship.`" />
    <div class="filters">
      <input v-model="q" class="input search" type="search" placeholder="Filter by name" aria-label="Filter teams by name">
      <UiChoice v-model="only" label="Show" :options="ONLY" />
      <span class="small muted count">{{ rows.length }} team{{ rows.length === 1 ? '' : 's' }}</span>
    </div>
    <section class="panel flush">
      <div class="table-scroll">
        <table class="data">
          <thead>
            <tr>
              <th class="sortable" :aria-sort="aria('name')" @click="by('name', false)">Team</th>
              <th class="sortable hide-md" :aria-sort="aria('country')" @click="by('country', false)">Country</th>
              <th class="sortable hide-sm" :aria-sort="aria('first_year')" @click="by('first_year', false)">Years</th>
              <th class="r sortable hide-sm" :aria-sort="aria('starts')" @click="by('starts')">Starts</th>
              <th class="r sortable" :aria-sort="aria('wins')" @click="by('wins')">Wins</th>
              <th class="r sortable hide-sm" :aria-sort="aria('one_twos')" @click="by('one_twos')">1-2s</th>
              <th class="r sortable hide-sm" :aria-sort="aria('poles')" @click="by('poles')">Poles</th>
              <th class="r sortable" :aria-sort="aria('championships')" @click="by('championships')">Titles</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in rows" :key="t.id">
              <td>
                <b><TeamName :id="t.id" :name="t.name" /></b>
                <span class="sub-line only-md">{{ t.country }}<span class="only-sm dot">{{ years(t.first_year, t.last_year) }}</span></span>
              </td>
              <td class="small ink-2 hide-md">{{ t.country }}</td>
              <td class="small num nowrap hide-sm">{{ years(t.first_year, t.last_year) }}</td>
              <td class="r hide-sm">{{ t.starts || '' }}</td>
              <td class="r"><b v-if="t.wins">{{ t.wins }}</b></td>
              <td class="r hide-sm">{{ t.one_twos || '' }}</td>
              <td class="r hide-sm">{{ t.poles || '' }}</td>
              <td class="r"><b v-if="t.championships">{{ t.championships }}</b></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.search {
  width: 220px;
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
</style>
