<script setup lang="ts">
import type { Season, Progression, ResultsGrid, GridCell } from '~/utils/types'

interface Rescore {
  system: { id: string; label: string; years: string }
  standings: { position: number; driver_id: string; name: string; points: number; wins: number; official_position: number | null; official_points: number | null }[]
}
interface PointsSystem { id: string; label: string; years: string }

const route = useRoute()
const year = computed(() => Number(route.params.year))
const { data: season, error } = await useApi<Season>(() => `/seasons/${year.value}`)
notFoundIf(error, 'Season')
const { data: progression } = await useApi<Progression>(() => `/seasons/${year.value}/progression`)
const { data: grid } = await useApi<ResultsGrid>(() => `/seasons/${year.value}/results-grid`)
const { data: systems } = await useApi<PointsSystem[]>('/points-systems')

const kind = useQueryState('standings', 'drivers') as Ref<'drivers' | 'constructors'>
const system = useQueryState('system', '2010')
const { data: rescore } = await useApi<Rescore>(() => `/seasons/${year.value}/rescore?system=${system.value}`)

const systemOptions = computed(() => (systems.value ?? []).map((s) => ({ value: s.id, label: s.label, sub: `Used ${s.years}` })))

const { data: order } = useFetch<{ rounds: { round: number; abbreviation: string }[]; teams: { id: string; name: string; gaps: (number | null)[]; average: number }[] }>(
  () => `/api/seasons/${year.value}/competitive-order`,
  { server: false, key: `order:${year.value}` },
)
const orderChart = useChartOption(() => (order.value ? competitiveOrderOption(order.value) : {}))


const champion = computed(() => season.value?.driver_standings[0])
const finished = computed(() => season.value?.races.filter((r) => r.completed) ?? [])
const inProgress = computed(() => !!season.value && finished.value.length < season.value.races.length)
const winners = computed(() => new Set(finished.value.map((r) => r.winner_id)).size)

usePageMeta({
  title: () => `${year.value} season`,
  description: () =>
    champion.value
      ? `${year.value} Formula 1 season: standings, every race result, points progression and the season under other points systems.`
      : `${year.value} Formula 1 season.`,
  eyebrow: () => (season.value?.era ? `Season · ${season.value.era.name} era` : 'Season'),
  stats: () => [
    [inProgress.value ? 'Leader' : 'Champion', champion.value?.name],
    [inProgress.value ? 'Leading team' : 'Constructors', season.value?.constructor_standings[0]?.name],
    ['Races', season.value?.races.length],
    ['Different winners', winners.value],
  ],
})

const teamOf = (id: string) => season.value?.driver_standings.find((d) => d.driver_id === id)?.constructors.at(-1)?.id ?? ''
const progressionChart = useChartOption(() =>
  progression.value ? progressionOption(progression.value, kind.value, teamOf, kind.value === 'drivers' ? 10 : 10) : {},
)

function cellClass(c: GridCell | null) {
  if (!c) return 'none'
  const p = c.position_number
  if (p == null) return 'out'
  if (p === 1) return 's6'
  if (p <= 3) return 's5'
  if (p <= 6) return 's4'
  if (p <= 10) return 's2'
  return 'plain'
}
function cellText(c: GridCell | null) {
  if (!c) return ''
  return c.position_number ?? (c.position_text === 'DNF' ? 'Ret' : c.position_text)
}
function cellTitle(c: GridCell | null, round: string) {
  if (!c) return ''
  const bits = [`${round}: ${c.position_number ? `P${c.position_number}` : c.position_text}`]
  if (c.grid) bits.push(`from P${c.grid}`)
  if (c.reason_retired) bits.push(c.reason_retired)
  if (c.points) bits.push(`${points(c.points)} pts`)
  if (c.pole_position) bits.push('pole')
  if (c.fastest_lap) bits.push('fastest lap')
  return bits.join(' · ')
}
</script>

<template>
  <div v-if="season">
    <PageHeader :title="`${season.year} season`" :crumbs="[{ to: '/seasons', label: 'Seasons' }, { label: String(season.year) }]">
      <template #sub>
        <template v-if="champion && !inProgress">
          Won by <NuxtLink class="link" :to="`/drivers/${champion.driver_id}`">{{ champion.name }}</NuxtLink>
          with {{ points(champion.points) }} points;
          {{ season.constructor_standings[0]?.name }} took the constructors' title.
        </template>
        <template v-else-if="champion">
          {{ finished.length }} of {{ season.races.length }} races run. {{ champion.name }} leads on {{ points(champion.points) }} points.
        </template>
      </template>
      <NuxtLink v-if="season.era" class="btn ghost" to="/eras" :title="season.era.engine">{{ season.era.name }} era</NuxtLink>
      <NuxtLink v-if="season.prev" class="btn" :to="`/seasons/${season.prev}`"><Icon name="left" :size="16" /> {{ season.prev }}</NuxtLink>
      <NuxtLink v-if="season.next" class="btn" :to="`/seasons/${season.next}`">{{ season.next }} <Icon name="right" :size="16" /></NuxtLink>
    </PageHeader>

    <div class="stack">
      <Tiles>
        <StatTile :label="inProgress ? 'Leader' : 'Champion'" :value="champion?.name" :hint="champion ? `${points(champion.points)} points · ${champion.wins} wins` : ''" :to="champion ? `/drivers/${champion.driver_id}` : undefined" />
        <StatTile :label="inProgress ? 'Leading team' : 'Constructors’ champion'" :value="season.constructor_standings[0]?.name" :hint="season.constructor_standings[0] ? `${points(season.constructor_standings[0].points)} points` : ''" :to="season.constructor_standings[0] ? `/constructors/${season.constructor_standings[0].constructor_id}` : undefined" />
        <StatTile label="Races" :value="season.races.length" :hint="inProgress ? `${finished.length} run so far` : `${season.races.filter((r) => r.has_sprint).length} with a sprint`" />
        <StatTile label="Different winners" :value="winners" :hint="`from ${season.driver_standings.length} drivers`" />
      </Tiles>

      <div class="grid-12">
        <Panel class="span-5" title="Standings" flush>
          <template #actions>
            <div class="segmented" role="tablist">
              <button :class="{ on: kind === 'drivers' }" @click="kind = 'drivers'">Drivers</button>
              <button :class="{ on: kind === 'constructors' }" @click="kind = 'constructors'">Teams</button>
            </div>
          </template>
          <div class="table-scroll standings">
            <table class="data">
              <thead>
                <tr><th class="c">Pos</th><th>{{ kind === 'drivers' ? 'Driver' : 'Team' }}</th><th class="r">Wins</th><th class="r">Pts</th></tr>
              </thead>
              <tbody v-if="kind === 'drivers'">
                <tr v-for="d in season.driver_standings" :key="d.driver_id">
                  <td class="c"><ResultPos :position="d.position" :text="d.position_text" /></td>
                  <td>
                    <NuxtLink :to="`/drivers/${d.driver_id}`"><b>{{ d.name }}</b></NuxtLink>
                    <div class="tiny muted row wrap" style="gap: 10px"><TeamName v-for="c in d.constructors" :id="c.id" :key="c.id" :name="c.name" /></div>
                  </td>
                  <td class="r">{{ d.wins || '' }}</td>
                  <td class="r"><b>{{ points(d.points) }}</b></td>
                </tr>
              </tbody>
              <tbody v-else>
                <tr v-for="c in season.constructor_standings" :key="c.constructor_id">
                  <td class="c"><ResultPos :position="c.position" :text="c.position_text" /></td>
                  <td><TeamName :id="c.constructor_id" :name="c.name" /><div class="tiny muted">{{ c.engine }}</div></td>
                  <td class="r">{{ c.wins || '' }}</td>
                  <td class="r"><b>{{ points(c.points) }}</b></td>
                </tr>
              </tbody>
            </table>
            <p v-if="kind === 'constructors' && !season.constructor_standings.length" class="empty">
              The constructors' championship started in 1958.
            </p>
          </div>
        </Panel>
        <Panel class="span-7" title="Points over the season" :note="`Top ten ${kind === 'drivers' ? 'drivers' : 'teams'}. Hover or tap a line to isolate it.`">
          <Chart v-if="progression?.rounds.length" :option="progressionChart" :height="420" :compact-height="340" label="Championship points after each round" share-id="points" />
          <p v-else class="empty">No races run yet.</p>
        </Panel>
      </div>

      <TitleOdds :year="season.year" :team-of="teamOf" />

      <Panel
        v-if="order?.teams.length"
        title="Competitive order"
        note="Each team's best qualifying lap at every race, as a percentage slower than the fastest car. Laps more than 5% off are left out."
      >
        <Chart :option="orderChart" :height="380" :compact-height="320" label="Gap of each team to the fastest car, race by race" share-id="competitive-order" />
        <p class="small muted">
          Season average:
          <template v-for="(t, i) in order.teams.slice(0, 6)" :key="t.id">{{ i ? ', ' : '' }}<b>{{ t.name }}</b> {{ t.average === 0 ? '0' : `+${t.average.toFixed(2)}` }}%</template>
        </p>
      </Panel>

      <Panel title="Races" flush>
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr><th class="r">Rd</th><th>Grand Prix</th><th class="hide-sm">Date</th><th>Winner</th><th class="hide-md">Team</th><th class="hide-md">Pole</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in season.races" :key="r.id">
                <td class="r muted">{{ r.round }}</td>
                <td>
                  <NuxtLink :to="`/races/${season.year}/${r.round}`"><b>{{ r.grand_prix }}</b></NuxtLink>
                  <span v-if="r.has_sprint" class="badge" style="margin-left: 6px">Sprint</span>
                  <div class="tiny muted">{{ r.circuit }}, {{ r.country }}<span class="only-sm dot">{{ date(r.date) }}</span></div>
                </td>
                <td class="nowrap small hide-sm">{{ date(r.date) }}</td>
                <td>
                  <NuxtLink v-if="r.winner_id" :to="`/drivers/${r.winner_id}`">{{ r.winner }}</NuxtLink><span v-else class="muted small">{{ r.completed ? '–' : 'Upcoming' }}</span>
                  <span v-if="r.winner_constructor" class="sub-line only-md">{{ r.winner_constructor }}</span>
                </td>
                <td class="hide-md"><TeamName v-if="r.winner_constructor_id" :id="r.winner_constructor_id" :name="r.winner_constructor!" /></td>
                <td class="small hide-md"><NuxtLink v-if="r.pole_id" :to="`/drivers/${r.pole_id}`">{{ r.pole }}</NuxtLink></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel v-if="grid?.rows.length" title="Every result" note="Darker blue is a better finish. Ret = retired, hover a cell for details." flush>
        <div class="table-scroll">
          <table class="data results-grid">
            <thead>
              <tr>
                <th class="sticky">Driver</th>
                <th v-for="r in grid.rounds" :key="r.id" class="c" :title="r.grand_prix">
                  <NuxtLink :to="`/races/${season.year}/${r.round}`">{{ r.abbreviation }}</NuxtLink>
                </th>
                <th class="r">Pts</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in grid.rows" :key="row.id">
                <td class="sticky nowrap"><span class="muted num pos-num">{{ row.position ?? '' }}</span> <NuxtLink :to="`/drivers/${row.id}`">{{ row.name }}</NuxtLink></td>
                <td v-for="(c, i) in row.results" :key="i" class="c cell" :class="cellClass(c)" :title="cellTitle(c, grid.rounds[i]!.grand_prix)">
                  {{ cellText(c) }}<span v-if="c?.pole_position" class="mark">•</span>
                </td>
                <td class="r"><b>{{ points(row.points) }}</b></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel id="what-if" title="What if: another points system" note="Grand Prix results only, every result counts, sprints left out, so systems compare fairly.">
        <div class="filters">
          <UiSelect v-model="system" label="Points system" :options="systemOptions" />
        </div>
        <div v-if="rescore" class="table-scroll">
          <table class="data">
            <thead><tr><th class="c">Pos</th><th>Driver</th><th class="r">Points</th><th class="r hide-sm">Wins</th><th class="r">Real result</th><th class="r hide-sm">Change</th></tr></thead>
            <tbody>
              <tr v-for="r in rescore.standings.slice(0, 12)" :key="r.driver_id" :class="{ changed: r.position === 1 && r.official_position !== 1 }">
                <td class="c"><ResultPos :position="r.position" /></td>
                <td><NuxtLink :to="`/drivers/${r.driver_id}`"><b>{{ r.name }}</b></NuxtLink></td>
                <td class="r"><b>{{ points(r.points) }}</b></td>
                <td class="r hide-sm">{{ r.wins || '' }}</td>
                <td class="r muted nowrap">{{ r.official_position ? `P${r.official_position}, ${points(r.official_points)} pts` : '–' }}</td>
                <td class="r hide-sm">
                  <span v-if="r.official_position && r.official_position !== r.position" :class="r.official_position > r.position ? 'up' : 'down'">
                    {{ r.official_position > r.position ? '▲' : '▼' }} {{ Math.abs(r.official_position - r.position) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="rescore && rescore.standings[0] && rescore.standings[0].official_position !== 1" class="callout small">
          Under this system <b>{{ rescore.standings[0].name }}</b> would have been champion.
        </p>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.standings {
  max-height: 520px;
  overflow-y: auto;
}
.results-grid {
  font-size: 12px;
}
.results-grid th,
.results-grid td {
  padding: 6px 4px;
}
.results-grid th a:hover {
  color: var(--ink);
}
.results-grid .sticky {
  position: sticky;
  left: 0;
  background: var(--surface);
  z-index: 1;
  padding-left: 16px;
  min-width: 170px;
}
.pos-num {
  display: inline-block;
  width: 18px;
  text-align: right;
  margin-right: 4px;
}
.cell {
  min-width: 34px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  border-left: 2px solid var(--surface);
}
.cell.s6 { background: var(--seq-6); color: var(--on-seq-6); }
.cell.s5 { background: var(--seq-5); color: var(--on-seq-5); }
.cell.s4 { background: var(--seq-3); color: var(--ink); }
.cell.s2 { background: var(--seq-1); }
.cell.plain { color: var(--ink-2); font-weight: 500; }
.cell.out { color: var(--muted); font-weight: 500; font-size: 11px; }
.mark { margin-left: 1px; }
.up { color: var(--good-ink); font-weight: 600; }
.down { color: var(--bad); font-weight: 600; }
.changed td { background: var(--accent-soft); }
.callout {
  background: var(--accent-soft);
  border-radius: 10px;
  padding: 10px 14px;
}
</style>
