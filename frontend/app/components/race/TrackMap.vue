<script setup lang="ts">
// Track map drawn from the reference lap's positions, rotated like the official map. With two laps, each
// mini-sector is coloured by the faster driver, and both cars can be replayed side by side in real time.
import type { Corner, TelemetryLap } from '~/utils/charts'

const props = defineProps<{
  laps: TelemetryLap[]
  rotation: number
  corners: Corner[]
  dominance?: { from_m: number; to_m: number; driver_id: string }[]
  colors: string[]
}>()

const base = computed(() => props.laps[0]!)
const angle = computed(() => (props.rotation * Math.PI) / 180)
function rotate(x: number, y: number): [number, number] {
  const c = Math.cos(angle.value)
  const s = Math.sin(angle.value)
  // SVG y grows downwards, so flip it.
  return [x * c - y * s, -(x * s + y * c)]
}
const points = computed(() => base.value.x.map((x, i) => rotate(x, base.value.y[i]!)))
const box = computed(() => {
  const xs = points.value.map((p) => p[0])
  const ys = points.value.map((p) => p[1])
  const pad = 900
  const minX = Math.min(...xs) - pad
  const minY = Math.min(...ys) - pad
  return { minX, minY, w: Math.max(...xs) - minX + pad, h: Math.max(...ys) - minY + pad }
})
const stroke = computed(() => Math.max(box.value.w, box.value.h) / 70)
const outline = computed(() => 'M' + points.value.map((p) => p.map((v) => v.toFixed(0)).join(' ')).join('L'))

const segments = computed(() => {
  if (!props.dominance?.length) return []
  const d = base.value.distance
  return props.dominance.map((s) => {
    const idx = d.map((v, i) => [v, i] as const).filter(([v]) => v >= s.from_m - 10 && v <= s.to_m + 10).map(([, i]) => i)
    const path = idx.length ? 'M' + idx.map((i) => points.value[i]!.map((v) => v.toFixed(0)).join(' ')).join('L') : ''
    const slot = props.laps.findIndex((l) => l.driver_id === s.driver_id)
    return { path, color: props.colors[slot] ?? props.colors[0] }
  })
})
const cornerLabels = computed(() =>
  props.corners.map((c) => {
    // Push the label outwards from the corner along the corner's angle.
    const a = ((c.angle + props.rotation) * Math.PI) / 180
    const [x, y] = rotate(c.x + Math.cos(a) * 700, c.y + Math.sin(a) * 700)
    return { x, y, label: `${c.number}${c.letter}` }
  }),
)

// Replay: one clock, each car placed by interpolating its own time-distance-position arrays.
const playing = ref(false)
const t = ref(0)
const end = computed(() => Math.max(...props.laps.map((l) => l.time[l.time.length - 1] ?? 0)))
let raf = 0
let last = 0
function frame(now: number) {
  if (!playing.value) return
  t.value = Math.min(end.value, t.value + (now - last) / 1000)
  last = now
  if (t.value >= end.value) playing.value = false
  else raf = requestAnimationFrame(frame)
}
function toggle() {
  if (playing.value) {
    playing.value = false
    cancelAnimationFrame(raf)
    return
  }
  if (t.value >= end.value) t.value = 0
  playing.value = true
  last = performance.now()
  raf = requestAnimationFrame(frame)
}
onBeforeUnmount(() => cancelAnimationFrame(raf))
watch(() => props.laps, () => {
  playing.value = false
  t.value = 0
})

function at(lap: TelemetryLap, time: number) {
  const ts = lap.time
  let i = ts.findIndex((v) => v >= time)
  if (i < 0) i = ts.length - 1
  if (i === 0) return { ...pos(lap, 0), d: 0 }
  const f = (time - ts[i - 1]!) / Math.max(1e-6, ts[i]! - ts[i - 1]!)
  const x = lap.x[i - 1]! + (lap.x[i]! - lap.x[i - 1]!) * f
  const y = lap.y[i - 1]! + (lap.y[i]! - lap.y[i - 1]!) * f
  const [rx, ry] = rotate(x, y)
  return { x: rx, y: ry, d: lap.distance[i - 1]! + (lap.distance[i]! - lap.distance[i - 1]!) * f }
}
function pos(lap: TelemetryLap, i: number) {
  const [x, y] = rotate(lap.x[i]!, lap.y[i]!)
  return { x, y }
}
const cars = computed(() => props.laps.map((l, i) => ({ ...at(l, t.value), color: props.colors[i], label: l.abbreviation ?? l.name })))
const gapNow = computed(() => {
  if (cars.value.length < 2) return null
  return cars.value[0]!.d - cars.value[1]!.d
})
</script>

<template>
  <div class="track">
    <svg :viewBox="`${box.minX} ${box.minY} ${box.w} ${box.h}`" role="img" :aria-label="dominance?.length ? 'Track map coloured by the faster driver in each section' : 'Track map'">
      <path :d="outline" class="outline" :stroke-width="stroke * 2.2" />
      <template v-if="segments.length">
        <path v-for="(s, i) in segments" :key="i" :d="s.path" :stroke="s.color" :stroke-width="stroke" class="seg" />
      </template>
      <path v-else :d="outline" class="seg" :stroke="colors[0]" :stroke-width="stroke" />
      <g class="corners">
        <text v-for="c in cornerLabels" :key="c.label" :x="c.x" :y="c.y" :font-size="stroke * 2.4">{{ c.label }}</text>
      </g>
      <g v-for="c in cars" :key="c.label">
        <circle :cx="c.x" :cy="c.y" :r="stroke * 1.6" :fill="c.color" class="car" :stroke-width="stroke * 0.5" />
      </g>
    </svg>
    <div class="controls">
      <button class="btn icon" type="button" :aria-label="playing ? 'Pause' : 'Play the laps'" @click="toggle">
        <svg v-if="!playing" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4v16l13-8z" fill="currentColor" /></svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h4v16H6zM14 4h4v16h-4z" fill="currentColor" /></svg>
      </button>
      <input v-model.number="t" type="range" min="0" :max="end" step="0.05" class="scrub" aria-label="Time into the lap">
      <span class="small num time">{{ t.toFixed(1) }}s</span>
    </div>
    <p v-if="gapNow != null && t > 0" class="small muted">
      {{ Math.abs(gapNow) < 1 ? 'Side by side' : `${cars[gapNow > 0 ? 0 : 1]!.label} ahead by ${Math.abs(gapNow).toFixed(0)} m` }}
    </p>
  </div>
</template>

<style scoped>
.track svg {
  width: 100%;
  aspect-ratio: 1.15;
  display: block;
}
.outline {
  fill: none;
  stroke: var(--surface-3);
  stroke-linejoin: round;
  stroke-linecap: round;
}
.seg {
  fill: none;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.corners text {
  fill: var(--muted);
  text-anchor: middle;
  dominant-baseline: middle;
  font-weight: 600;
}
.car {
  stroke: var(--surface);
}
.controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.scrub {
  flex: 1;
  accent-color: var(--accent);
}
.time {
  min-width: 48px;
  text-align: right;
}
</style>
