<script setup lang="ts">
// The race told lap by lap: the lap chart with safety-car bands, next to a timeline of what happened.
// Clicking a moment marks its lap on the chart and highlights the drivers involved.
import type { RaceLaps } from '~/utils/types'
import type { Period } from '~/utils/charts'

interface StoryEvent {
  lap: number
  kind: 'start' | 'lead' | 'pit' | 'retire' | 'sc' | 'vsc' | 'red' | 'penalty' | 'fastest' | 'finish'
  drivers: string[]
  text: string
  cheap?: boolean
}
interface Story {
  has_timing: boolean
  periods: Period[]
  events: StoryEvent[]
  rain: boolean
}

const props = defineProps<{ year: number; round: number; laps: RaceLaps }>()
const { data: story } = useFetch<Story>(() => `/api/races/${props.year}/${props.round}/story`, {
  server: false,
  key: `story:${props.year}:${props.round}`,
})

const filter = useQueryState('events', 'key')
const lapParam = useQueryState('lap', '')
const selected = computed(() => (lapParam.value ? Number(lapParam.value) : null))
const FILTERS = [
  { value: 'key', label: 'Key moments' },
  { value: 'all', label: 'Everything' },
  { value: 'pit', label: 'Pit stops' },
]
const KEY = new Set(['start', 'lead', 'retire', 'sc', 'vsc', 'red', 'penalty', 'fastest', 'finish'])
const events = computed(() =>
  (story.value?.events ?? []).filter((e) =>
    filter.value === 'all' ? true : filter.value === 'pit' ? e.kind === 'pit' : KEY.has(e.kind) || e.cheap,
  ),
)
const focus = ref<string[]>([])
function pick(e: StoryEvent, i: number) {
  if (selected.value === e.lap && activeIndex.value === i) {
    lapParam.value = ''
    focus.value = []
    activeIndex.value = -1
    return
  }
  lapParam.value = String(e.lap)
  focus.value = e.drivers
  activeIndex.value = i
}
const activeIndex = ref(-1)

const chart = useChartOption(() => withLapMarks(lapChartOption(props.laps, focus.value), story.value?.periods, selected.value))
const LABEL: Record<StoryEvent['kind'], string> = {
  start: 'Start',
  lead: 'Lead',
  pit: 'Pit',
  retire: 'Out',
  sc: 'SC',
  vsc: 'VSC',
  red: 'Red',
  penalty: 'Penalty',
  fastest: 'Fastest',
  finish: 'Finish',
}
</script>

<template>
  <div class="grid-12">
    <Panel class="span-8" title="Race story" :note="story?.has_timing ? 'Lap chart with safety-car periods. Pick a moment on the right to mark its lap.' : 'Lap chart. Safety-car periods and penalties are recorded from 2018.'">
      <template v-if="story?.rain" #actions><span class="chip">Rain during the race</span></template>
      <Chart :option="chart" :height="Math.max(460, laps.drivers.length * 26)" :compact-height="Math.max(420, laps.drivers.length * 22)" label="Lap chart with race events" share-id="story" />
      <div class="legend small muted">
        <span><i class="band sc" /> Safety car</span>
        <span><i class="band vsc" /> Virtual safety car</span>
        <span><i class="band red" /> Red flag</span>
        <span><i class="dot" /> Pit stop</span>
      </div>
    </Panel>
    <Panel class="span-4 timeline-panel" title="What happened" flush>
      <template #actions>
        <UiChoice v-model="filter" label="Show" :options="FILTERS" collapse="always" />
      </template>
      <ol v-if="story" class="timeline">
        <li v-for="(e, i) in events" :key="i">
          <button type="button" :class="{ on: activeIndex === i }" @click="pick(e, i)">
            <span class="lap num">L{{ e.lap }}</span>
            <span class="tag" :class="e.kind">{{ LABEL[e.kind] }}</span>
            <span class="text">{{ e.text }}</span>
          </button>
        </li>
        <li v-if="!events.length"><EmptyState title="Nothing to show" text="Try another filter." /></li>
      </ol>
      <div v-else class="skeleton" style="height: 400px; margin: 0 16px 16px" />
    </Panel>
  </div>
</template>

<style scoped>
.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.band {
  width: 14px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
.band.sc { background: rgba(250, 178, 25, 0.45); }
.band.vsc { background: rgba(250, 178, 25, 0.22); }
.band.red { background: rgba(208, 59, 59, 0.4); }
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-2);
  display: inline-block;
}
.timeline {
  list-style: none;
  margin: 0;
  padding: 0 8px 12px;
  max-height: 640px;
  overflow-y: auto;
}
.timeline button {
  width: 100%;
  display: grid;
  grid-template-columns: 34px 58px 1fr;
  gap: 8px;
  align-items: start;
  text-align: left;
  border: 0;
  background: none;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.timeline button:hover {
  background: var(--surface-2);
}
.timeline button.on {
  background: var(--accent-soft);
}
.lap {
  color: var(--muted);
  font-weight: 600;
  padding-top: 1px;
}
.tag {
  font-size: 11px;
  font-weight: 650;
  border-radius: 6px;
  padding: 2px 6px;
  text-align: center;
  background: var(--surface-3);
  color: var(--ink-2);
}
.tag.lead,
.tag.finish {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.tag.sc,
.tag.vsc {
  background: rgba(250, 178, 25, 0.22);
  color: var(--ink);
}
.tag.red,
.tag.retire {
  background: rgba(208, 59, 59, 0.16);
  color: var(--ink);
}
.text {
  color: var(--ink);
  line-height: 1.4;
}
@media (max-width: 1080px) {
  .timeline {
    max-height: 420px;
  }
}
</style>
