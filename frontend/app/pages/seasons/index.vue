<script setup lang="ts">
import type { SeasonSummary } from '~/utils/types'

const { data: seasons } = await useApi<SeasonSummary[]>('/seasons')
usePageMeta({ title: 'Seasons', description: 'Every Formula 1 season since 1950 with its champions.' })

const decades = computed(() => {
  const out: { decade: number; seasons: SeasonSummary[] }[] = []
  for (const s of seasons.value ?? []) {
    const d = Math.floor(s.year / 10) * 10
    let group = out.find((g) => g.decade === d)
    if (!group) out.push((group = { decade: d, seasons: [] }))
    group.seasons.push(s)
  }
  return out
})
</script>

<template>
  <div>
    <PageHeader title="Seasons" :sub="`${seasons?.length ?? ''} world championships, newest first.`" />
    <div class="stack">
      <section v-for="g in decades" :key="g.decade">
        <h2 class="decade">{{ g.decade }}s</h2>
        <div class="cards">
          <NuxtLink v-for="s in g.seasons" :key="s.year" :to="`/seasons/${s.year}`" class="card card-link">
            <div class="spread">
              <span class="year">{{ s.year }}</span>
              <span class="small muted">{{ s.races }} races</span>
            </div>
            <div v-if="s.driver_champion" class="small">
              <span class="muted">Driver</span> <b>{{ s.driver_champion }}</b>
            </div>
            <div v-else class="small muted">In progress</div>
            <div v-if="s.constructor_champion" class="small row">
              <span class="muted">Team</span>
              <span class="team-bar" :style="{ background: teamColor(s.constructor_champion_id), height: '12px' }" />
              <b>{{ s.constructor_champion }}</b>
            </div>
          </NuxtLink>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.decade {
  margin-bottom: 10px;
  color: var(--ink-2);
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
  gap: 10px;
}
.card {
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.year {
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.02em;
}
</style>
