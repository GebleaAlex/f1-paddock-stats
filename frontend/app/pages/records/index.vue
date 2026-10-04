<script setup lang="ts">
interface Board { id: string; label: string; entity: string; hint: string | null }
interface BoardData {
  id: string
  label: string
  hint: string | null
  entity: 'driver' | 'constructor'
  unit: string | null
  rows: { rank: number; id: string; name: string; value: number; detail?: string | null }[]
}

const { data: boards } = await useApi<Board[]>('/records')
const board = useQueryState('board', 'wins')
const { data } = await useApi<BoardData>(() => `/records/${board.value}?limit=50`)
usePageMeta({
  title: () => (data.value ? `Records: ${data.value.label}` : 'Records'),
  description: 'Formula 1 all-time records: wins, poles, titles, streaks, youngest and oldest winners.',
  stats: () => (data.value?.rows ?? []).slice(0, 4).map((r) => [r.name, String(r.value)]),
})
const max = computed(() => Math.max(...(data.value?.rows ?? []).map((r) => r.value), 1))
const drivers = computed(() => boards.value?.filter((b) => b.entity === 'driver') ?? [])
const teams = computed(() => boards.value?.filter((b) => b.entity === 'constructor') ?? [])
const boardOptions = computed(() =>
  (boards.value ?? []).map((b) => ({ value: b.id, label: b.label, sub: b.hint ?? undefined, group: b.entity === 'driver' ? 'Drivers' : 'Teams' })),
)
function fmt(v: number, unit: string | null) {
  if (unit === '%') return `${v}%`
  if (unit === 'years') return `${v.toFixed(2)} years`
  return points(v)
}
</script>

<template>
  <div>
    <PageHeader title="Records" sub="All-time leaderboards. Ties share a rank." />
    <div class="layout">
      <UiSelect v-model="board" class="board-select" label="Record" :options="boardOptions" block />
      <nav class="boards" aria-label="Records">
        <div class="eyebrow">Drivers</div>
        <button v-for="b in drivers" :key="b.id" :class="{ on: b.id === board }" @click="board = b.id">{{ b.label }}</button>
        <div class="eyebrow" style="margin-top: 12px">Teams</div>
        <button v-for="b in teams" :key="b.id" :class="{ on: b.id === board }" @click="board = b.id">{{ b.label }}</button>
      </nav>
      <Panel v-if="data" :title="data.label" :note="data.hint ?? undefined" flush>
        <table class="data">
          <tbody>
            <tr v-for="r in data.rows" :key="r.id + (r.detail ?? '')">
              <td class="r muted" style="width: 48px">{{ r.rank }}</td>
              <td>
                <NuxtLink v-if="data.entity === 'driver'" :to="`/drivers/${r.id}`"><b>{{ r.name }}</b></NuxtLink>
                <b v-else><TeamName :id="r.id" :name="r.name" /></b>
                <span v-if="r.detail" class="small muted"> · {{ r.detail }}</span>
              </td>
              <td class="bar-cell"><span class="bar" :style="{ width: `${(r.value / max) * 100}%` }" /></td>
              <td class="r nowrap"><b>{{ fmt(r.value, data.unit) }}</b></td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: var(--gap);
  align-items: start;
}
.boards {
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: sticky;
  top: 80px;
}
.boards button {
  text-align: left;
  border: 0;
  background: none;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--ink-2);
  cursor: pointer;
}
.boards button:hover {
  background: var(--surface-2);
}
.boards button.on {
  background: var(--accent-soft);
  color: var(--ink);
  font-weight: 600;
}
.bar-cell {
  width: 30%;
}
.board-select {
  display: none;
}
.bar {
  display: block;
  height: 8px;
  border-radius: 0 4px 4px 0;
  background: var(--series-1);
}
@media (max-width: 820px) {
  .layout {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .boards {
    display: none;
  }
  .board-select {
    display: block;
  }
  .bar-cell {
    width: 22%;
  }
}
</style>
