<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { DriverDetail, Teammate } from '~/utils/types'

const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error } = await useApi<DriverDetail>(() => `/drivers/${id.value}`)
notFoundIf(error, 'Driver')

const d = computed(() => data.value?.driver)
const { data: telemetryLaps } = useFetch<{ year: number; round: number; type: string; grand_prix: string; lap: number; lap_time_ms: number; best_ms: number }[]>(
  () => `/api/drivers/${id.value}/telemetry-laps`,
  { server: false, key: `tl:${id.value}` },
)
const showAllLaps = ref(false)
const { data: rating } = useFetch<{ ratings: { model: string; skill: number; comparisons: number }[]; ranks: Record<string, number> }>(
  () => `/api/ratings/${id.value}`,
  { server: false, key: `rating:${id.value}` },
)
const combined = computed(() => rating.value?.ratings.find((r) => r.model === 'combined'))
const teams = computed(() => {
  const seen = new Map<string, string>()
  for (const s of data.value?.seasons ?? []) for (const c of s.constructors ?? []) seen.set(c.id, c.name)
  return [...seen.entries()].map(([id, name]) => ({ id, name }))
})
const firstYear = computed(() => data.value?.seasons[0]?.year)
const lastYear = computed(() => data.value?.seasons.at(-1)?.year)
const winRate = computed(() => (d.value && d.value.starts ? (d.value.wins / d.value.starts) * 100 : null))
const ageNow = computed(() => (d.value?.date_of_birth ? age(d.value.date_of_birth, d.value.date_of_death) : null))

usePageMeta({
  title: () => d.value?.name ?? 'Driver',
  description: () =>
    d.value
      ? `${d.value.name}: ${d.value.starts} starts, ${d.value.wins} wins, ${d.value.podiums} podiums, ${d.value.poles} poles and ${d.value.championships} world titles. Seasons, teammates and head-to-heads.`
      : undefined,
  eyebrow: () => (d.value ? `Driver · ${d.value.nationality ?? ''}` : undefined),
  stats: () => (d.value ? [['World titles', d.value.championships], ['Wins', d.value.wins], ['Podiums', d.value.podiums], ['Poles', d.value.poles]] : []),
})

const positionChart = useChartOption<EChartsOption>(() => {
  const seasons = data.value?.seasons ?? []
  const max = Math.max(10, ...seasons.map((s) => s.position ?? 0))
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (p: unknown) => {
        const s = seasons[(p as { dataIndex: number }[])[0]!.dataIndex]!
        return `<b>${s.year}</b><br>${s.position ? `Championship: ${ordinal(s.position)}` : 'Not classified'}<br>${points(s.points)} points · ${s.wins} wins<br>${(s.constructors ?? []).map((c) => c.name).join(', ')}`
      },
    },
    xAxis: { type: 'category', data: seasons.map((s) => String(s.year)) },
    yAxis: { type: 'value', inverse: true, min: 1, max, minInterval: 1, axisLabel: { formatter: (v: number) => ordinal(v) } },
    series: [
      {
        type: 'line',
        data: seasons.map((s) => s.position),
        connectNulls: false,
        color: seriesColor(1),
        symbolSize: 8,
        itemStyle: { borderColor: cssVar('--surface'), borderWidth: 2 },
        markArea: {
          silent: true,
          itemStyle: { color: cssVar('--accent-soft') },
          data: [[{ yAxis: 0.5 }, { yAxis: 1.5 }]],
        },
      },
    ],
  }
})

const winsChart = useChartOption<EChartsOption>(() => {
  const seasons = data.value?.seasons ?? []
  return {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { left: 8, right: 8, top: 32, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: seasons.map((s) => String(s.year)) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: 'Wins', type: 'bar', data: seasons.map((s) => s.wins), color: seriesColor(1), barMaxWidth: 16, barGap: '10%' },
      { name: 'Podiums', type: 'bar', data: seasons.map((s) => s.podiums), color: seriesColor(2), barMaxWidth: 16 },
      { name: 'Poles', type: 'bar', data: seasons.map((s) => s.poles), color: seriesColor(3), barMaxWidth: 16 },
    ],
  }
})

const CATEGORY_LABELS: Record<string, string> = {
  accident: 'Crash',
  technical: 'Technical',
  rules: 'Penalty / DSQ',
  other: 'Other',
  DSQ: 'Disqualified',
  DNS: 'Did not start',
  DNQ: 'Did not qualify',
  DNPQ: 'Did not pre-qualify',
  EX: 'Excluded',
  DNP: 'Did not practise',
}
const finishChart = useChartOption<EChartsOption>(() => {
  const f = data.value?.finishes ?? []
  const byPos = f.filter((x) => /^\d+$/.test(x.outcome)).sort((a, b) => Number(a.outcome) - Number(b.outcome))
  const rest = f.filter((x) => !/^\d+$/.test(x.outcome)).sort((a, b) => b.n - a.n)
  const cats = [...byPos.map((x) => `P${x.outcome}`), ...rest.map((x) => CATEGORY_LABELS[x.outcome] ?? x.outcome)]
  const vals = [
    ...byPos.map((x) => ({ value: x.n, itemStyle: { color: seriesColor(1) } })),
    ...rest.map((x) => ({ value: x.n, itemStyle: { color: cssVar('--axis') } })),
  ]
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: 'item', formatter: (p: unknown) => { const t = p as { name: string; value: number }; return `<b>${t.name}</b>: ${t.value} race${t.value === 1 ? '' : 's'}` } },
    xAxis: { type: 'category', data: cats, axisLabel: { interval: 0, rotate: cats.length > 18 ? 45 : 0, fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: vals, barMaxWidth: 22 }],
  }
})

function duel(won: number, lost: number) {
  const total = won + lost
  return total ? (won / total) * 100 : 50
}
const mates = computed<Teammate[]>(() => data.value?.teammates ?? [])
const FAMILY: Record<string, string> = {
  CHILD: 'Child', PARENT: 'Parent', SIBLING: 'Sibling', SIBLINGS_CHILD: 'Nephew or niece', PARENTS_SIBLING: 'Uncle or aunt',
  GRANDCHILD: 'Grandchild', GRANDPARENT: 'Grandparent', COUSIN: 'Cousin',
}
</script>

<template>
  <div v-if="data && d">
    <PageHeader :title="d.name" :crumbs="[{ to: '/drivers', label: 'Drivers' }, { label: [d.nationality, d.permanent_number ? `#${d.permanent_number}` : null, d.abbreviation].filter(Boolean).join(' · ') }]">
      <template #sub>
        <template v-if="d.date_of_birth">
          Born {{ date(d.date_of_birth, { dateStyle: 'long' }) }}<template v-if="d.place_of_birth"> in {{ d.place_of_birth }}</template><template v-if="d.date_of_death">, died {{ date(d.date_of_death, { dateStyle: 'long' }) }} aged {{ ageNow }}</template><template v-else> ({{ ageNow }})</template>.
        </template>
        Raced {{ years(firstYear, lastYear) }} for
        <template v-for="(t, i) in teams" :key="t.id"><NuxtLink class="link" :to="`/constructors/${t.id}`">{{ t.name }}</NuxtLink>{{ i < teams.length - 2 ? ', ' : i === teams.length - 2 ? ' and ' : '' }}</template>.
      </template>
      <NuxtLink class="btn" :to="`/compare?drivers=${d.id}`"><Icon name="plus" :size="16" /> Compare</NuxtLink>
    </PageHeader>

    <div class="stack">
      <Tiles>
        <StatTile label="World titles" :value="d.championships" :hint="d.best_championship_position ? `Best: ${ordinal(d.best_championship_position)}` : 'Never classified'" />
        <StatTile label="Wins" :value="d.wins" :hint="winRate != null ? `${winRate.toFixed(1)}% of starts` : ''" />
        <StatTile label="Podiums" :value="d.podiums" />
        <StatTile label="Poles" :value="d.poles" />
        <StatTile label="Starts" :value="d.starts" :hint="d.entries > d.starts ? `${d.entries} entries` : ''" />
        <StatTile label="Points" :value="points(d.points)" />
        <StatTile label="Fastest laps" :value="d.fastest_laps" />
        <StatTile
          v-if="combined && combined.comparisons >= 40"
          label="Rating across eras"
          :value="`${combined.skill > 0 ? '+' : ''}${combined.skill.toFixed(2)}`"
          :hint="`Ranked ${ordinal(rating!.ranks.combined)} of all drivers`"
          to="/ratings"
        />
        <StatTile label="Laps raced" :value="num(d.laps)" :hint="d.grand_slams ? `${d.grand_slams} grand slams` : ''" />
      </Tiles>

      <div class="grid-12">
        <Panel class="span-6" title="Championship position" note="Final position each season; the band marks the title.">
          <Chart :option="positionChart" :height="280" label="Championship position by season" share-id="championships" />
        </Panel>
        <Panel class="span-6" title="Wins, podiums and poles per season">
          <Chart :option="winsChart" :height="280" label="Wins, podiums and poles by season" />
        </Panel>
      </div>

      <Panel title="Teammates" :note="`Qualifying and race duels against every teammate. Race duels count only races both finished. Gap: median qualifying gap, negative means ${d.last_name ?? d.name} was faster.`" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr>
                <th>Teammate</th><th class="hide-md">Team</th><th class="hide-md">Years</th><th class="r hide-sm">Races</th>
                <th class="c">Qualifying</th><th class="c">Race</th><th class="r hide-md">Points</th><th class="r hide-sm">Gap</th><th class="hide-sm" />
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in mates" :key="m.driver_id">
                <td>
                  <NuxtLink :to="`/teammates/${d.id}/${m.driver_id}`"><b>{{ m.name }}</b></NuxtLink>
                  <span class="sub-line only-md">{{ m.constructors.join(', ') }} · {{ years(m.first_year, m.last_year) }}<span class="only-sm dot">{{ m.races }} races</span></span>
                </td>
                <td class="small ink-2 hide-md">{{ m.constructors.join(', ') }}</td>
                <td class="small num nowrap hide-md">{{ years(m.first_year, m.last_year) }}</td>
                <td class="r hide-sm">{{ m.races }}</td>
                <td><DuelBar :won="m.quali_won" :lost="m.quali_lost" /></td>
                <td><DuelBar :won="m.race_won" :lost="m.race_lost" /></td>
                <td class="r nowrap small hide-md">{{ points(m.points_me) }}–{{ points(m.points_mate) }}</td>
                <td class="r nowrap hide-sm" :class="m.median_gap_pct == null ? 'muted' : m.median_gap_pct < 0 ? 'good' : 'bad'">{{ pct(m.median_gap_pct) }}</td>
                <td class="r hide-sm"><NuxtLink class="link small nowrap" :to="`/teammates/${d.id}/${m.driver_id}`">Head-to-head</NuxtLink></td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-if="!mates.length" title="No teammates to compare" text="This driver never finished a race alongside a teammate in the same team." />
        </div>
      </Panel>

      <div class="grid-12">
        <Panel class="span-7" title="How races ended" note="Finishing positions, then the reasons for not finishing.">
          <Chart :option="finishChart" :height="260" :compact-height="240" label="Count of finishing positions and retirement reasons" />
        </Panel>
        <Panel class="span-5" title="Milestones">
          <dl class="facts">
            <template v-for="(label, key) in { first_race: 'First race', first_win: 'First win', last_win: 'Last win', last_race: 'Last race' }" :key="key">
              <template v-if="data.milestones[key]">
                <dt>{{ label }}</dt>
                <dd><NuxtLink class="link" :to="`/races/${data.milestones[key]!.year}/${data.milestones[key]!.round}`">{{ data.milestones[key]!.year }} {{ data.milestones[key]!.grand_prix }}</NuxtLink></dd>
              </template>
            </template>
            <template v-if="data.family.length">
              <dt>Family</dt>
              <dd>
                <span v-for="(f, i) in data.family" :key="f.driver_id">
                  <NuxtLink class="link" :to="`/drivers/${f.driver_id}`">{{ f.name }}</NuxtLink> <span class="muted">({{ FAMILY[f.type] ?? f.type.toLowerCase() }})</span><template v-if="i < data.family.length - 1">, </template>
                </span>
              </dd>
            </template>
          </dl>
        </Panel>
      </div>

      <Panel
        v-if="telemetryLaps?.length"
        title="Qualifying laps with telemetry"
        :note="`${telemetryLaps.length} qualifying sessions from 2018. Open one to compare the lap with anyone in the session.`"
        flush
      >
        <div class="table-scroll">
          <table class="data">
            <thead><tr><th>Session</th><th class="r">Lap time</th><th class="r">Gap to fastest</th><th /></tr></thead>
            <tbody>
              <tr v-for="t in (showAllLaps ? telemetryLaps : telemetryLaps.slice(0, 8))" :key="`${t.year}-${t.round}-${t.type}`">
                <td><b>{{ t.year }} {{ t.grand_prix }}</b> <span class="small muted">{{ t.type === 'SQ' ? 'Sprint qualifying' : 'Qualifying' }}</span></td>
                <td class="r num">{{ lapTime(t.lap_time_ms) }}</td>
                <td class="r num">{{ t.lap_time_ms === t.best_ms ? 'Fastest' : `+${((t.lap_time_ms - t.best_ms) / 1000).toFixed(3)}s` }}</td>
                <td class="r"><NuxtLink class="link small nowrap" :to="`/races/${t.year}/${t.round}?view=telemetry&session=${t.type}&a=${d.id}`">Telemetry</NuxtLink></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="telemetryLaps.length > 8 && !showAllLaps" class="more-row"><button class="btn" @click="showAllLaps = true">Show all {{ telemetryLaps.length }}</button></div>
      </Panel>

      <Panel title="Seasons" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr><th>Year</th><th>Team</th><th class="c">Pos</th><th class="r">Points</th><th class="r hide-sm">Starts</th><th class="r">Wins</th><th class="r hide-sm">Podiums</th><th class="r hide-sm">Poles</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in data.seasons.slice().reverse()" :key="s.year">
                <td><NuxtLink class="link" :to="`/seasons/${s.year}`"><b>{{ s.year }}</b></NuxtLink></td>
                <td><span class="row wrap" style="gap: 12px"><TeamName v-for="c in s.constructors ?? []" :id="c.id" :key="c.id" :name="c.name" /></span></td>
                <td class="c"><ResultPos :position="s.position" :text="s.position_text ?? '–'" /></td>
                <td class="r">{{ points(s.points) }}</td>
                <td class="r hide-sm">{{ s.starts }}</td>
                <td class="r"><b v-if="s.wins">{{ s.wins }}</b></td>
                <td class="r hide-sm">{{ s.podiums || '' }}</td>
                <td class="r hide-sm">{{ s.poles || '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.facts {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 16px;
  margin: 0;
}
.facts dt {
  color: var(--muted);
  font-size: 13px;
}
.facts dd {
  margin: 0;
}
.good { color: var(--good-ink); font-weight: 600; }
.more-row {
  display: flex;
  justify-content: center;
  padding: 0 var(--pad) var(--pad);
}
.bad { color: var(--bad); font-weight: 600; }
</style>
