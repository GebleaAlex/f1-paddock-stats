<script setup lang="ts">
import type { Meta, Season, Progression, RaceDetail } from '~/utils/types'

const { data: meta } = await useApi<Meta>('/meta')
const year = computed(() => meta.value?.latest_race?.year ?? new Date().getFullYear())
const { data: season } = await useApi<Season>(() => `/seasons/${year.value}`)
const { data: progression } = await useApi<Progression>(() => `/seasons/${year.value}/progression`)
const latest = meta.value?.latest_race
const { data: race } = await useApi<RaceDetail>(() => (latest ? `/races/${latest.year}/${latest.round}` : '/races/0/0'))

usePageMeta({ title: 'Formula 1 statistics, 1950 to today', description: 'Every season, race, driver, team and circuit since 1950, lap-by-lap race stories, tyres and telemetry, teammate duels and an open driver rating.', })

const teamOf = (id: string) => season.value?.driver_standings.find((d) => d.driver_id === id)?.constructors.at(-1)?.id ?? ''
const progressionChart = useChartOption(() => (progression.value ? progressionOption(progression.value, 'drivers', teamOf, 6) : {}))
const podium = computed(() => race.value?.results.filter((r) => r.position && r.position <= 3) ?? [])

const FEATURES = [
  {
    to: '/teammates/lewis-hamilton/nico-rosberg',
    title: 'Teammate duels',
    text: 'Every pairing since 1950: who out-qualified whom, race wins, points share and the median qualifying gap.',
  },
  {
    to: '/compare?drivers=ayrton-senna,alain-prost,michael-schumacher,max-verstappen',
    title: 'Compare across eras',
    text: 'Careers side by side, by start number or by age, for up to four drivers.',
  },
  {
    to: '/seasons/1988?system=2010#what-if',
    title: 'What if',
    text: 'Re-score any season under another points system. Under today’s points, 1988 has a different champion.',
  },
  {
    to: '/races/2021/22?view=laps',
    title: 'Lap charts',
    text: 'Positions, gaps and lap times for every lap of every race since 1996.',
  },
]
</script>

<template>
  <div class="stack">
    <section class="hero">
      <div class="grow">
        <h1>Formula 1, from 1950 to the last lap.</h1>
        <p class="lead">
          Every season, race, driver, team and circuit in one place, with lap-by-lap data from 1996. Free, open source,
          and every page is a link you can share.
        </p>
      </div>
      <Tiles v-if="meta" class="counts">
        <StatTile label="Seasons" :value="meta.counts.seasons" to="/seasons" />
        <StatTile label="Races" :value="num(meta.counts.races)" to="/seasons" />
        <StatTile label="Drivers" :value="num(meta.counts.drivers)" to="/drivers" />
        <StatTile label="Laps recorded" :value="num(meta.counts.laps)" hint="1996 to today" />
      </Tiles>
    </section>

    <div class="grid-12">
      <Panel v-if="race" class="span-5" :title="`${race.race.year} ${race.race.grand_prix}`" :note="`Latest race · ${date(race.race.date)} · ${race.race.circuit}`">
        <template #actions>
          <NuxtLink class="btn" :to="`/races/${race.race.year}/${race.race.round}`">Full result</NuxtLink>
        </template>
        <ol class="podium">
          <li v-for="r in podium" :key="r.driver_id">
            <ResultPos :position="r.position" />
            <div class="grow">
              <NuxtLink :to="`/drivers/${r.driver_id}`" class="name">{{ r.driver }}</NuxtLink>
              <div class="small muted"><TeamName :id="r.constructor_id" :name="r.constructor" /></div>
            </div>
            <span class="small muted num">{{ r.position === 1 ? r.time : r.gap }}</span>
          </li>
        </ol>
        <p v-if="meta?.next_race" class="small ink-2 next">
          Next: <b>{{ meta.next_race.grand_prix }}</b>, {{ date(meta.next_race.date) }} at {{ meta.next_race.circuit }}
        </p>
      </Panel>

      <Panel v-if="season && progression" class="span-7" :title="`${season.year} championship`" note="Points after each round, top six">
        <template #actions>
          <NuxtLink class="btn" :to="`/seasons/${season.year}`">Season</NuxtLink>
        </template>
        <Chart :option="progressionChart" :height="280" :compact-height="260" label="Championship points over the season" />
      </Panel>
    </div>

    <div class="grid-12">
      <Panel v-if="season" class="span-6" title="Drivers' standings" flush>
        <div class="table-scroll">
          <table class="data">
            <tbody>
              <tr v-for="d in season.driver_standings.slice(0, 10)" :key="d.driver_id">
                <td class="c" style="width: 48px"><ResultPos :position="d.position" :text="d.position_text" /></td>
                <td>
                  <NuxtLink :to="`/drivers/${d.driver_id}`"><b>{{ d.name }}</b></NuxtLink>
                  <div class="small muted"><TeamName v-for="c in d.constructors" :id="c.id" :key="c.id" :name="c.name" /></div>
                </td>
                <td class="r"><b>{{ points(d.points) }}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel v-if="season" class="span-6" title="Constructors' standings" flush>
        <div class="table-scroll">
          <table class="data">
            <tbody>
              <tr v-for="c in season.constructor_standings.slice(0, 10)" :key="c.constructor_id">
                <td class="c" style="width: 48px"><ResultPos :position="c.position" :text="c.position_text" /></td>
                <td><TeamName :id="c.constructor_id" :name="c.name" /><div class="small muted">{{ c.engine }}</div></td>
                <td class="r"><b>{{ points(c.points) }}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>

    <section>
      <h2 class="section-title">Explore</h2>
      <div class="features">
        <NuxtLink v-for="f in FEATURES" :key="f.to" :to="f.to" class="feature card-link">
          <h3>{{ f.title }}</h3>
          <p class="small ink-2">{{ f.text }}</p>
          <span class="small link">Open <Icon name="right" :size="14" /></span>
        </NuxtLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  gap: var(--gap);
  align-items: flex-end;
  flex-wrap: wrap;
}
.hero h1 {
  font-size: clamp(30px, 4.4vw, 46px);
  letter-spacing: -0.03em;
  max-width: 16ch;
}
.lead {
  margin-top: 12px;
  font-size: 17px;
  color: var(--ink-2);
  max-width: 58ch;
}
.counts {
  flex: 1 1 420px;
  max-width: 640px;
}
@media (max-width: 640px) {
  .lead {
    font-size: 15px;
  }
}
.podium {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.podium li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--grid);
}
.podium li:last-child {
  border-bottom: 0;
}
.podium .name {
  font-weight: 650;
}
.next {
  margin-top: auto;
}
.section-title {
  margin-bottom: 12px;
}
.features {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
  gap: 12px;
}
.feature {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.feature .link {
  margin-top: auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
</style>
