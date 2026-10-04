<script setup lang="ts">
// Safety cars, red flags and wet races at one circuit, from the timing data (2018+).
interface ConditionsRace {
  year: number
  round: number
  grand_prix: string
  safety_cars: number
  virtual_safety_cars: number
  red_flags: number
  neutralised_laps: number
  race_laps: number
  rain: boolean
  wet: boolean
  wet_share: number
}
interface Summary {
  races: number
  safety_car_races: number
  safety_cars: number
  virtual_safety_cars: number
  red_flag_races: number
  wet_races: number
  rain_races: number
  neutralised_pct: number | null
  safety_car_chance: number
  safety_cars_per_race: number
  first_year: number
}
interface Conditions {
  races: ConditionsRace[]
  summary: Summary | null
  rank: { safety_car: number; of: number } | null
  method: { wet_race: string; rain: string; safety_car: string }
}

const props = defineProps<{ circuitId: string }>()
const { data } = useFetch<Conditions>(() => `/api/circuits/${props.circuitId}/conditions`, {
  server: false,
  key: `conditions:${props.circuitId}`,
})
const s = computed(() => data.value?.summary)
function weather(r: ConditionsRace) {
  if (r.wet) return { label: `Wet · ${Math.round(r.wet_share * 100)}% of laps on wet tyres`, cls: 'wet' }
  if (r.rain) return { label: 'Some rain, run on dry tyres', cls: 'rain' }
  return { label: 'Dry', cls: 'dry' }
}
</script>

<template>
  <Panel title="Safety cars and weather" :note="s ? `From the timing data, ${s.races} race${s.races === 1 ? '' : 's'} since ${s.first_year}.` : 'Recorded from 2018.'">
    <div v-if="!data" class="skeleton" style="height: 160px" />
    <EmptyState v-else-if="!s" title="No timing data for this circuit" text="Safety cars, red flags and the weather are recorded from 2018. This circuit has not held a race with timing data loaded." />
    <div v-else class="stack">
      <Tiles>
        <StatTile
          label="Races with a safety car"
          :value="`${Math.round(s.safety_car_chance * 100)}%`"
          :hint="`${s.safety_car_races} of ${s.races}${data.rank ? ` · ${ordinal(data.rank.safety_car)} most of ${data.rank.of} circuits` : ''}`"
        />
        <StatTile label="Safety cars per race" :value="s.safety_cars_per_race.toFixed(1)" :hint="`Plus ${s.virtual_safety_cars} virtual safety car${s.virtual_safety_cars === 1 ? '' : 's'} in all`" />
        <StatTile label="Laps behind a safety car" :value="s.neutralised_pct != null ? `${s.neutralised_pct}%` : '–'" hint="Safety car, virtual safety car or red flag" />
        <StatTile label="Wet races" :value="s.wet_races" :hint="s.rain_races ? `Rain fell during ${s.rain_races}` : 'No rain recorded'" />
      </Tiles>
      <div class="table-scroll">
        <table class="data">
          <thead>
            <tr><th>Year</th><th class="r">Safety cars</th><th class="r">Virtual</th><th class="r hide-sm">Red flags</th><th>Weather</th><th class="r hide-sm">Laps neutralised</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in data.races" :key="`${r.year}-${r.round}`">
              <td class="nowrap"><NuxtLink class="link" :to="`/races/${r.year}/${r.round}?view=story`"><b>{{ r.year }}</b></NuxtLink></td>
              <td class="r num"><b v-if="r.safety_cars">{{ r.safety_cars }}</b><span v-else class="muted">0</span></td>
              <td class="r num">{{ r.virtual_safety_cars || '' }}</td>
              <td class="r num hide-sm">{{ r.red_flags || '' }}</td>
              <td class="small"><span class="wx" :class="weather(r).cls" />{{ weather(r).label }}</td>
              <td class="r num hide-sm">{{ r.neutralised_laps }} of {{ r.race_laps }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="tiny muted">{{ data.method.safety_car }}. Wet race: {{ data.method.wet_race.toLowerCase() }}.</p>
    </div>
  </Panel>
</template>

<style scoped>
.wx {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: 1px;
  border: 1px solid var(--border-strong);
}
.wx.wet {
  background: #1f6fd1;
  border-color: #1f6fd1;
}
.wx.rain {
  background: #2fa84f;
  border-color: #2fa84f;
}
.wx.dry {
  background: transparent;
}
</style>
