<script setup lang="ts">
// The championship's regulation eras: engine formula, what changed, who won.
interface Era {
  id: string
  from: number
  to: number | null
  name: string
  engine: string
  summary: string
  races: number
  top_team: string | null
  top_driver: string | null
  champions: { year: number; id: string; name: string }[]
}

const { data: eras } = await useApi<Era[]>('/eras')
usePageMeta({ title: 'Regulation eras', description: 'The engine formulas and rule changes that shaped each era of Formula 1, and who won in each.' })
</script>

<template>
  <div>
    <PageHeader title="Regulation eras" sub="The rules decide what kind of car wins. Engine formulas and the biggest technical changes since 1950, and who made the most of them." :crumbs="[{ to: '/seasons', label: 'Seasons' }, { label: 'Eras' }]" />
    <ol class="eras">
      <li v-for="e in eras" :key="e.id" class="panel era">
        <div class="when">
          <span class="years">{{ e.from }}–{{ e.to ?? '' }}</span>
          <span class="small muted">{{ e.races }} races</span>
        </div>
        <div class="grow body">
          <h2>{{ e.name }}</h2>
          <p class="small ink-2"><b>Engines:</b> {{ e.engine }}</p>
          <p class="small ink-2">{{ e.summary }}</p>
          <p v-if="e.top_team" class="small">
            Most wins: <b>{{ e.top_driver }}</b> among drivers, <b>{{ e.top_team }}</b> among teams.
          </p>
          <div class="champions">
            <NuxtLink v-for="c in e.champions" :key="c.year" :to="`/seasons/${c.year}`" class="chip" :title="`${c.year}: ${c.name}`">
              <span class="muted">{{ c.year }}</span> {{ c.name.split(' ').slice(-1)[0] }}
            </NuxtLink>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.eras {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.era {
  flex-direction: row;
  gap: 20px;
}
.when {
  width: 110px;
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.years {
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.02em;
}
.body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.champions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
@media (max-width: 640px) {
  .era {
    flex-direction: column;
    gap: 8px;
  }
  .when {
    flex-direction: row;
    align-items: baseline;
    gap: 10px;
    width: auto;
  }
}
</style>
