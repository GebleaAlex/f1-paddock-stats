<script setup lang="ts">
// One chart component for the whole site: ECharts with an SVG renderer and a theme built from the CSS tokens,
// so every chart gets the same quiet chrome (hairline grid, 2px lines, crosshair tooltips) in light and dark mode.
import { use, registerTheme } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { BarChart, LineChart, ScatterChart, CustomChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DataZoomComponent,
  AxisPointerComponent,
} from 'echarts/components'
import { LegacyGridContainLabel } from 'echarts/features'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([
  SVGRenderer,
  LegacyGridContainLabel,
  BarChart,
  LineChart,
  ScatterChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DataZoomComponent,
  AxisPointerComponent,
])

const props = withDefaults(
  defineProps<{ option: EChartsOption; height?: number | string; compactHeight?: number; label?: string; shareId?: string }>(),
  { height: 360, compactHeight: undefined, label: undefined, shareId: undefined },
)

const { mode } = useTheme()
const themeName = computed(() => `paddock-${mode.value}`)
const registered = new Set<string>()

function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function ensureTheme(name: string) {
  if (registered.has(name)) return
  const ink = token('--ink')
  const ink2 = token('--ink-2')
  const muted = token('--muted')
  const grid = token('--grid')
  const axis = token('--axis')
  const surface = token('--surface')
  const border = token('--border-strong')
  const axisCommon = {
    axisLine: { lineStyle: { color: axis } },
    axisTick: { show: false },
    axisLabel: { color: muted, fontSize: 11 },
    splitLine: { lineStyle: { color: grid, width: 1 } },
    nameTextStyle: { color: muted, fontSize: 11 },
  }
  registerTheme(name, {
    color: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => token(`--series-${i}`)),
    backgroundColor: 'transparent',
    textStyle: { fontFamily: token('--font'), color: ink2 },
    categoryAxis: { ...axisCommon, splitLine: { show: false } },
    valueAxis: { ...axisCommon, axisLine: { show: false } },
    legend: { textStyle: { color: ink2, fontSize: 12 }, icon: 'roundRect', itemWidth: 14, itemHeight: 4 },
    tooltip: {
      backgroundColor: surface,
      borderColor: border,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: ink, fontSize: 12 },
      extraCssText: 'border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.18);',
      axisPointer: { lineStyle: { color: axis, width: 1 }, crossStyle: { color: axis } },
    },
    line: { lineStyle: { width: 2 }, symbolSize: 8, symbol: 'circle', smooth: false },
    bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
  })
  registered.add(name)
}

const ready = ref(false)
onMounted(() => {
  ensureTheme(themeName.value)
  ready.value = true
})
watch(themeName, (n) => ensureTheme(n))

// Phones get a shorter chart (unless the page asks for a specific compact height) so it fits on screen.
const narrow = ref(false)
let mq: MediaQueryList | undefined
const onMq = () => (narrow.value = !!mq?.matches)
onMounted(() => {
  mq = window.matchMedia('(max-width: 640px)')
  onMq()
  mq.addEventListener('change', onMq)
})
onBeforeUnmount(() => mq?.removeEventListener('change', onMq))
const style = computed(() => {
  const h = narrow.value && typeof props.height === 'number' ? (props.compactHeight ?? Math.min(props.height, 300)) : props.height
  return { height: typeof h === 'number' ? `${h}px` : h }
})

// Tooltips stay inside the chart (they would run off a phone screen otherwise) and follow taps on touch screens.
const finalOption = computed<EChartsOption>(() => {
  const o = props.option as EChartsOption & { tooltip?: Record<string, unknown> }
  if (!o || !o.tooltip || Array.isArray(o.tooltip)) return o
  return { ...o, tooltip: { confine: true, enterable: false, ...o.tooltip } } as EChartsOption
})

// Sharing: download as PNG, link straight to this chart, or embed it. An embedded page shows only this chart.
const route = useRoute()
const root = ref<HTMLElement | null>(null)
const vchart = ref<{ getDataURL: (o: object) => string } | null>(null)
const menu = ref(false)
const done = ref('')
const domId = computed(() => (props.shareId ? `chart-${props.shareId}` : undefined))
function pageUrl(extra: Record<string, string> = {}) {
  const url = new URL(window.location.href)
  url.hash = ''
  for (const [k, v] of Object.entries(extra)) url.searchParams.set(k, v)
  return url
}
function flash(text: string) {
  done.value = text
  setTimeout(() => {
    done.value = ''
    menu.value = false
  }, 1400)
}
function download() {
  const url = vchart.value?.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: token('--surface') })
  if (!url) return
  const a = document.createElement('a')
  const name = (document.title.split(' · ')[0] || 'chart').replace(/[^a-z0-9]+/gi, '-').toLowerCase()
  a.href = url
  a.download = `${name}-${props.shareId}.png`
  a.click()
  flash('Image saved')
}
async function copyLink() {
  const url = pageUrl()
  url.hash = domId.value ?? ''
  await navigator.clipboard.writeText(url.toString())
  flash('Link copied')
}
async function copyEmbed() {
  const url = pageUrl({ embed: props.shareId! })
  const h = (root.value?.offsetHeight ?? 360) + 90
  const title = `${props.label ?? 'Chart'} · Paddock Stats`
  const code = `<iframe src="${url}" width="100%" height="${h}" style="border:0" loading="lazy" title="${title}"></iframe>`
  await navigator.clipboard.writeText(code)
  flash('Embed code copied')
}
function isolate() {
  // Hide everything on the page except the panel holding this chart.
  let node: HTMLElement | null = root.value?.closest('.panel') ?? root.value
  while (node && node.parentElement && !node.parentElement.classList.contains('embed-shell')) {
    for (const sib of Array.from(node.parentElement.children)) if (sib !== node) (sib as HTMLElement).style.display = 'none'
    node.style.gridColumn = '1 / -1'
    node = node.parentElement
  }
}
onMounted(() => {
  if (props.shareId && route.query.embed === props.shareId) nextTick(() => setTimeout(isolate, 50))
})
</script>

<template>
  <div :id="domId" ref="root" class="chart" :style="style" role="img" :aria-label="label">
    <ClientOnly>
      <VChart v-if="ready" ref="vchart" :key="themeName" :option="finalOption" :theme="themeName" autoresize :update-options="{ notMerge: true }" />
      <template #fallback><div class="skeleton" style="height: 100%" /></template>
    </ClientOnly>
    <div v-if="shareId && !route.query.embed" class="share">
      <button class="btn ghost icon share-btn" type="button" aria-label="Share this chart" :aria-expanded="menu" @click="menu = !menu">
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.8" fill="currentColor" /><circle cx="12" cy="12" r="1.8" fill="currentColor" /><circle cx="19" cy="12" r="1.8" fill="currentColor" /></svg>
      </button>
      <div v-if="menu" class="share-menu" role="menu" @mouseleave="menu = false">
        <p v-if="done" class="small done">{{ done }}</p>
        <template v-else>
          <button type="button" role="menuitem" @click="download">Download image</button>
          <button type="button" role="menuitem" @click="copyLink">Copy link to this chart</button>
          <button type="button" role="menuitem" @click="copyEmbed">Copy embed code</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart {
  width: 100%;
  min-width: 0;
  position: relative;
  scroll-margin-top: 90px;
}
.share {
  position: absolute;
  top: -6px;
  right: -6px;
  z-index: 5;
}
.share-btn {
  width: 30px;
  height: 30px;
  opacity: 0.55;
}
.chart:hover .share-btn,
.share-btn:focus-visible,
.share-btn[aria-expanded='true'] {
  opacity: 1;
}
.share-menu {
  position: absolute;
  right: 0;
  top: 34px;
  min-width: 210px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
  padding: 6px;
  display: flex;
  flex-direction: column;
}
.share-menu button {
  border: 0;
  background: none;
  text-align: left;
  padding: 9px 10px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}
.share-menu button:hover {
  background: var(--surface-2);
}
.done {
  padding: 9px 10px;
  color: var(--good-ink);
  font-weight: 600;
}
@media (hover: none) {
  .share-btn {
    opacity: 0.8;
  }
}
</style>
