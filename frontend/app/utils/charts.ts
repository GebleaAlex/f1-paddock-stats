// ECharts option builders. Pages pass plain API data in and get an option out, so the chart rules
// (2px lines, end labels instead of a 20-entry legend, crosshair tooltips sorted by value) live in one place.
import type { EChartsOption, SeriesOption } from 'echarts'
import type { Progression, RaceLaps } from './types'
import { cssVar, driverStyles, teamColor } from './teams'
import { lapTime } from './format'

type Tip = { seriesName: string; value: unknown; color: string; seriesId?: string; data?: unknown }

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

function key(color: string, dashed = false): string {
  return `<span style="display:inline-block;width:14px;height:0;border-top:2px ${dashed ? 'dashed' : 'solid'} ${color};vertical-align:middle;margin-right:6px"></span>`
}

const GRID = { left: 8, right: 56, top: 16, bottom: 28, containLabel: true }

/**
 * Which end labels to show so none collide: walk the lines from the top by their final value and keep a label
 * only when it is at least `minGap` (in data units) from the last kept one. Hidden ones stay in the legend
 * and the tooltip.
 */
export function labelled(finals: Record<string, number | undefined>, minGap: number): Set<string> {
  const keep = new Set<string>()
  let last: number | undefined
  const entries = Object.entries(finals).filter((e): e is [string, number] => e[1] != null).sort((a, b) => b[1] - a[1])
  for (const [id, v] of entries) {
    if (last == null || Math.abs(last - v) >= minGap) {
      keep.add(id)
      last = v
    }
  }
  return keep
}

/** Position by lap for every driver, grid position as lap 0, pit stops marked with dots. */
export function lapChartOption(data: RaceLaps, focus: string[] = []): EChartsOption {
  const styles = driverStyles(data.drivers)
  const pits = new Set(data.pit_stops.map((p) => `${p.driver_id}:${p.lap}`))
  const n = data.drivers.length
  const series: SeriesOption[] = data.drivers.map((d) => {
    const laps = data.laps[d.driver_id] ?? []
    const st = styles[d.driver_id]!
    const dim = focus.length > 0 && !focus.includes(d.driver_id)
    const points = [
      ...(d.grid ? [{ value: [0, d.grid] }] : []),
      ...laps.map(([lap, pos]) => ({
        value: [lap, pos],
        symbol: pits.has(`${d.driver_id}:${lap}`) ? 'circle' : 'none',
        symbolSize: 7,
      })),
    ]
    return {
      id: d.driver_id,
      name: d.abbreviation || d.driver,
      type: 'line',
      data: points,
      showSymbol: true,
      color: st.color,
      lineStyle: { width: dim ? 1 : 2, type: st.dashed ? [5, 3] : 'solid', opacity: dim ? 0.18 : 1 },
      itemStyle: { opacity: dim ? 0.18 : 1, borderColor: cssVar('--surface'), borderWidth: 2 },
      endLabel: { show: !dim, formatter: '{a}', color: cssVar('--ink-2'), fontSize: 11, fontWeight: 600, distance: 6 },
      emphasis: { focus: 'series', lineStyle: { width: 3 } },
      z: dim ? 1 : 2,
    } as SeriesOption
  })
  return {
    animation: false,
    grid: { ...GRID, right: 52 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params: unknown) => {
        const list = (params as Tip[]).slice().sort((a, b) => (a.value as number[])[1]! - (b.value as number[])[1]!)
        const lap = (list[0]?.value as number[] | undefined)?.[0]
        const rows = list
          .map((p) => {
            const st = styles[p.seriesId ?? '']
            return `<div>${key(p.color, st?.dashed)}<b>P${(p.value as number[])[1]}</b> ${esc(p.seriesName)}</div>`
          })
          .join('')
        return `<div style="font-weight:600;margin-bottom:4px">${lap === 0 ? 'Grid' : `Lap ${lap}`}</div><div style="columns:2;column-gap:16px">${rows}</div>`
      },
    },
    xAxis: { type: 'value', min: 0, max: data.race.laps || 'dataMax', name: 'Lap', nameLocation: 'end', minInterval: 1 },
    yAxis: { type: 'value', inverse: true, min: 1, max: n, interval: 1, axisLabel: { formatter: 'P{value}' } },
    series,
  }
}

/** Cumulative race time per driver per lap, the base for gap charts. */
export function cumulative(data: RaceLaps): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const d of data.drivers) {
    let t = 0
    const arr: number[] = []
    for (const [lap, , ms] of data.laps[d.driver_id] ?? []) {
      t += ms
      arr[lap] = t
    }
    out[d.driver_id] = arr
  }
  return out
}

/**
 * Gap to a reference over the race ("race trace"). Reference "leader" means whoever led at that lap.
 * Values are seconds behind the reference; the axis is inverted so the front of the race is at the top.
 */
export function gapChartOption(data: RaceLaps, reference: string, focus: string[] = [], cap = 60): EChartsOption {
  const styles = driverStyles(data.drivers)
  const cum = cumulative(data)
  const maxLap = Math.max(0, ...Object.values(data.laps).map((l) => l.length ? l[l.length - 1]![0] : 0))
  const refTime = (lap: number): number | undefined => {
    if (reference !== 'leader') return cum[reference]?.[lap]
    let best: number | undefined
    for (const arr of Object.values(cum)) {
      const v = arr[lap]
      if (v != null && (best == null || v < best)) best = v
    }
    return best
  }
  const pits = new Set(data.pit_stops.map((p) => `${p.driver_id}:${p.lap}`))
  const finals: Record<string, number | undefined> = {}
  const series: SeriesOption[] = data.drivers.map((d) => {
    const st = styles[d.driver_id]!
    const dim = focus.length > 0 && !focus.includes(d.driver_id)
    const pts: { value: [number, number]; symbol: string; symbolSize: number }[] = []
    for (let lap = 1; lap <= maxLap; lap++) {
      const t = cum[d.driver_id]?.[lap]
      const r = refTime(lap)
      if (t == null || r == null) continue
      pts.push({ value: [lap, +((t - r) / 1000).toFixed(3)], symbol: pits.has(`${d.driver_id}:${lap}`) ? 'circle' : 'none', symbolSize: 7 })
    }
    const end = pts.at(-1)?.value[1]
    if (!dim && end != null && Math.abs(end) <= cap) finals[d.driver_id] = -end
    return {
      id: d.driver_id,
      name: d.abbreviation || d.driver,
      type: 'line',
      data: pts,
      color: st.color,
      lineStyle: { width: dim ? 1 : 2, type: st.dashed ? [5, 3] : 'solid', opacity: dim ? 0.18 : 1 },
      itemStyle: { opacity: dim ? 0.18 : 1 },
      endLabel: { show: false, formatter: '{a}', color: cssVar('--ink-2'), fontSize: 11, fontWeight: 600, distance: 6 },
      emphasis: { focus: 'series', lineStyle: { width: 3 } },
      clip: true,
    } as SeriesOption
  })
  // Label only line ends that do not collide (about 3.5% of the axis apart).
  const shown = labelled(finals, cap * 0.035)
  for (const sr of series as { id: string; endLabel: { show: boolean } }[]) sr.endLabel.show = shown.has(sr.id)
  return {
    animation: false,
    grid: { ...GRID, right: 52 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = (params as Tip[]).slice().sort((a, b) => (a.value as number[])[1]! - (b.value as number[])[1]!)
        const lap = (list[0]?.value as number[] | undefined)?.[0]
        const rows = list
          .map((p) => {
            const v = (p.value as number[])[1]!
            const txt = v === 0 ? '—' : `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}s`
            return `<div>${key(p.color, styles[p.seriesId ?? '']?.dashed)}<b style="display:inline-block;min-width:52px">${txt}</b>${esc(p.seriesName)}</div>`
          })
          .join('')
        return `<div style="font-weight:600;margin-bottom:4px">Lap ${lap}</div><div style="columns:2;column-gap:16px">${rows}</div>`
      },
    },
    xAxis: { type: 'value', min: 1, max: maxLap || 'dataMax', name: 'Lap', minInterval: 1 },
    yAxis: {
      type: 'value',
      inverse: true,
      min: (v: { min: number }) => Math.max(v.min, -cap),
      max: (v: { max: number }) => Math.min(v.max, cap),
      axisLabel: { formatter: (v: number) => (v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v)}s`) },
    },
    series,
  }
}

/** Cumulative championship points over a season. Shows the top `limit` entries, others available on hover. */
export function progressionOption(
  data: Progression,
  kind: 'drivers' | 'constructors',
  teamOf: (id: string) => string,
  limit = 10,
): EChartsOption {
  const entries = data[kind].slice(0, limit)
  const styles = driverStyles(entries.map((e) => ({ driver_id: e.id, constructor_id: kind === 'drivers' ? teamOf(e.id) : e.id })))
  const top = Math.max(1, ...entries.map((e) => e.points.at(-1) ?? 0))
  const show = labelled(Object.fromEntries(entries.map((e) => [e.id, e.points.at(-1)])), top * 0.04)
  return {
    animation: false,
    legend: { type: 'scroll', top: 0, left: 0, right: 0 },
    grid: { ...GRID, top: 40, right: 64 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = (params as (Tip & { dataIndex: number })[]).slice().sort((a, b) => (b.value as number) - (a.value as number))
        const r = data.rounds[list[0]?.dataIndex ?? 0]
        return (
          `<div style="font-weight:600;margin-bottom:4px">After round ${r?.round} · ${esc(r?.grand_prix ?? '')}</div>` +
          list.map((p) => `<div>${key(p.color, styles[p.seriesId ?? '']?.dashed)}<b style="display:inline-block;min-width:40px">${p.value}</b>${esc(p.seriesName)}</div>`).join('')
        )
      },
    },
    xAxis: { type: 'category', data: data.rounds.map((r) => r.abbreviation), boundaryGap: false, axisLabel: { interval: 'auto' } },
    yAxis: { type: 'value' },
    series: entries.map((e) => {
      const st = styles[e.id]!
      return {
        id: e.id,
        name: e.name,
        type: 'line',
        data: e.points,
        showSymbol: false,
        color: st.color,
        lineStyle: { width: 2, type: st.dashed ? [5, 3] : 'solid' },
        endLabel: {
          show: show.has(e.id),
          formatter: (p: { seriesName: string }) => p.seriesName.replace(/ (Jr|Sr)\.?$/, '').split(' ').at(-1) ?? '',
          color: cssVar('--ink-2'),
          fontSize: 11,
          fontWeight: 600,
        },
        emphasis: { focus: 'series' },
      } as SeriesOption
    }),
  }
}

/** Grid position against finishing position: one line per classified driver. */
export function slopeOption(rows: { driver_id: string; abbreviation: string; constructor_id: string; grid: number | null; position: number | null }[]): EChartsOption {
  const valid = rows.filter((r) => r.grid && r.position)
  const n = Math.max(...valid.map((r) => Math.max(r.grid!, r.position!)), 1)
  const styles = driverStyles(valid)
  return {
    animation: false,
    grid: { left: 48, right: 48, top: 16, bottom: 24 },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const t = p as Tip & { data: { name: string; grid: number; position: number } }
        const g = t.data.grid - t.data.position
        return `<b>${esc(t.seriesName)}</b><br>Grid P${t.data.grid} → finished P${t.data.position} (${g > 0 ? '+' : ''}${g})`
      },
    },
    xAxis: { type: 'category', data: ['Grid', 'Finish'], boundaryGap: false, axisLine: { show: false }, axisLabel: { fontWeight: 600 } },
    yAxis: { type: 'value', inverse: true, min: 1, max: n, interval: 1, show: false },
    series: valid.map((r) => {
      const st = styles[r.driver_id]!
      const point = { grid: r.grid, position: r.position }
      return {
        name: r.abbreviation,
        type: 'line',
        data: [
          { value: r.grid, ...point, label: { show: true, position: 'left', formatter: r.abbreviation, color: cssVar('--ink-2'), fontSize: 11 } },
          { value: r.position, ...point, label: { show: true, position: 'right', formatter: r.abbreviation, color: cssVar('--ink-2'), fontSize: 11 } },
        ],
        color: st.color,
        symbolSize: 8,
        lineStyle: { width: 2, type: st.dashed ? [5, 3] : 'solid' },
        emphasis: { focus: 'series' },
      } as SeriesOption
    }),
  }
}

export { teamColor }

// ---------- Phase 3: neutralisations, tyres, pace ----------

export interface Period {
  kind: 'sc' | 'vsc' | 'red'
  label: string
  from_lap: number
  to_lap: number
}

/** Shaded lap ranges for safety cars (amber), virtual safety cars (lighter) and red flags (red), with a short tag. */
export function neutralBands(periods: Period[] | undefined) {
  if (!periods?.length) return undefined
  const fill = { sc: 'rgba(250,178,25,0.13)', vsc: 'rgba(250,178,25,0.06)', red: 'rgba(208,59,59,0.12)' }
  const tag = { sc: 'SC', vsc: 'VSC', red: 'Red flag' }
  return {
    silent: true,
    data: periods.map((p) => [
      {
        xAxis: p.from_lap - 0.5,
        itemStyle: { color: fill[p.kind] },
        label: { show: true, position: 'insideTop', formatter: tag[p.kind], color: cssVar('--muted'), fontSize: 10 },
      },
      { xAxis: p.to_lap + 0.5 },
    ]),
  }
}

/** Adds neutralisation bands (and an optional highlighted lap) to a lap-based chart option. */
export function withLapMarks(option: EChartsOption, periods?: Period[], lap?: number | null): EChartsOption {
  const series = (option.series as SeriesOption[] | undefined) ?? []
  if (!series.length) return option
  const first = { ...(series[0] as object) } as Record<string, unknown>
  const bands = neutralBands(periods)
  if (bands) first.markArea = bands
  if (lap) {
    first.markLine = {
      silent: true,
      symbol: 'none',
      lineStyle: { color: cssVar('--accent'), width: 1.5, type: 'solid' },
      label: { formatter: `Lap ${lap}`, color: cssVar('--accent-ink'), fontSize: 11 },
      data: [{ xAxis: lap }],
    }
  }
  return { ...option, series: [first, ...series.slice(1)] as SeriesOption[] }
}

export const COMPOUNDS: Record<string, { label: string; short: string; color: string; ink: string }> = {
  SOFT: { label: 'Soft', short: 'S', color: '#e8102d', ink: '#ffffff' },
  MEDIUM: { label: 'Medium', short: 'M', color: '#f2c200', ink: '#0b0b0b' },
  HARD: { label: 'Hard', short: 'H', color: '#c9c9c9', ink: '#0b0b0b' },
  INTERMEDIATE: { label: 'Intermediate', short: 'I', color: '#2fa84f', ink: '#ffffff' },
  WET: { label: 'Wet', short: 'W', color: '#1f6fd1', ink: '#ffffff' },
}
export function compound(c: string | null | undefined) {
  return (c && COMPOUNDS[c]) || { label: c ? c.toLowerCase() : 'Unknown', short: '?', color: '#8a8a8a', ink: '#ffffff' }
}

export interface Stint {
  stint: number
  compound: string | null
  from_lap: number
  to_lap: number
  laps: number
  fresh?: boolean | null
  tyre_age_at_start?: number | null
  clean_laps?: number
  degradation_s_per_lap?: number | null
  median_corrected_ms?: number | null
}

export interface StrategyDriver {
  driver_id: string
  abbreviation: string | null
  name: string
  constructor_id: string
  constructor: string
  position: number | null
  position_text: string
  laps: number
  stints: Stint[]
}

/** Tyre strategy: one bar per driver in finishing order, a segment per stint in its compound colour. */
export function strategyOption(drivers: StrategyDriver[], totalLaps: number, periods?: Period[]): EChartsOption {
  const rows = drivers.slice().reverse()
  const maxStints = Math.max(1, ...rows.map((d) => d.stints.length))
  const neutral = [cssVar('--seq-3'), cssVar('--seq-5')]
  const series: SeriesOption[] = Array.from({ length: maxStints }, (_, i) => ({
    name: `Stint ${i + 1}`,
    type: 'bar',
    stack: 'stints',
    barWidth: 16,
    data: rows.map((d) => {
      const st = d.stints[i]
      if (!st) return null
      const c = st.compound ? compound(st.compound) : null
      return {
        value: st.laps,
        itemStyle: { color: c ? c.color : neutral[i % 2], borderColor: cssVar('--surface'), borderWidth: 1, borderRadius: 3 },
        label: c && st.laps >= 4 ? { show: true, formatter: c.short, color: c.ink, fontSize: 10, fontWeight: 700 } : { show: false },
        stint: st,
      }
    }),
  })) as SeriesOption[]
  if (periods?.length) (series[0] as Record<string, unknown>).markArea = neutralBands(periods)
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 20, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const t = p as { dataIndex: number; data: { stint: Stint } }
        const d = rows[t.dataIndex]!
        const st = t.data.stint
        const c = st.compound ? compound(st.compound).label : 'Stint'
        const age = st.tyre_age_at_start ? `, ${st.tyre_age_at_start} laps old` : st.fresh ? ', new' : ''
        const wear =
          st.degradation_s_per_lap != null
            ? `<br>Wear: ${st.degradation_s_per_lap > 0 ? '+' : ''}${st.degradation_s_per_lap.toFixed(3)} s per lap`
            : ''
        return `<b>${esc(d.name)}</b><br>${c}${age}: laps ${st.from_lap}–${st.to_lap} (${st.laps})${wear}`
      },
    },
    xAxis: { type: 'value', name: 'Lap', max: totalLaps || 'dataMax', minInterval: 1 },
    yAxis: { type: 'category', data: rows.map((d) => d.abbreviation || d.name), axisLabel: { fontWeight: 600 } },
    series,
  }
}

export interface PaceLap {
  lap: number
  time_ms: number | null
  corrected_ms: number | null
  compound: string | null
  tyre_life: number | null
  clean: boolean
  neutral: string | null
}

/** Lap times of chosen drivers: lines in the series colour, dots in the tyre colour (2018+). */
export function paceOption(
  laps: Record<string, PaceLap[]>,
  names: Record<string, string>,
  ids: string[],
  colors: string[],
  opts: { corrected: boolean; cleanOnly: boolean; periods?: Period[] },
): EChartsOption {
  const series: SeriesOption[] = ids.map((id, i) => {
    // Laps that are filtered out stay as gaps (null), so lines break instead of bridging a safety car.
    const rows = (laps[id] ?? []).map((r) => ((opts.cleanOnly ? r.clean : r.time_ms) ? r : { ...r, time_ms: null, corrected_ms: null }))
    const color = colors[i]!
    return {
      id,
      name: names[id] ?? id,
      type: 'line',
      color,
      lineStyle: { width: 2 },
      connectNulls: false,
      symbolSize: 7,
      data: rows.map((r) => ({
        value: [r.lap, r.time_ms == null ? null : ((opts.corrected ? r.corrected_ms : r.time_ms) ?? 0) / 1000],
        itemStyle: r.compound ? { color: compound(r.compound).color, borderColor: color, borderWidth: 2 } : undefined,
        lapInfo: r,
      })),
      endLabel: { show: true, formatter: '{a}', color: cssVar('--ink-2'), fontSize: 11, fontWeight: 600 },
    } as SeriesOption
  })
  const option: EChartsOption = {
    animation: false,
    legend: { top: 0, left: 0 },
    grid: { ...GRID, top: 36, right: 64 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = (params as (Tip & { data: { lapInfo: PaceLap } })[]).filter((p) => (p.value as (number | null)[])[1] != null)
        const lap = (list[0]?.value as number[] | undefined)?.[0]
        return (
          `<div style="font-weight:600;margin-bottom:4px">Lap ${lap}</div>` +
          list
            .map((p) => {
              const r = p.data.lapInfo
              const tyre = r.compound ? ` · ${compound(r.compound).label}${r.tyre_life ? `, ${r.tyre_life} laps` : ''}` : ''
              return `<div>${key(p.color)}<b>${lapTime(Math.round((p.value as number[])[1]! * 1000))}</b> ${esc(p.seriesName)}<span style="opacity:.7">${tyre}</span></div>`
            })
            .join('')
        )
      },
    },
    xAxis: { type: 'value', name: 'Lap', min: 1, max: 'dataMax', minInterval: 1 },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => lapTime(v * 1000) } },
    series,
  }
  return withLapMarks(option, opts.periods)
}

// ---------- Phase 4: telemetry ----------

export interface TelemetryLap {
  driver_id: string
  name: string
  abbreviation: string | null
  lap: number
  lap_time_ms: number
  distance: number[]
  time: number[]
  speed: number[]
  throttle: number[]
  brake: number[]
  gear: number[]
  rpm: number[]
  drs: number[]
  x: number[]
  y: number[]
  sectors: { s1_ms: number | null; s2_ms: number | null; s3_ms: number | null; compound: string | null; tyre_life: number | null } | null
}

export interface Corner {
  number: number
  letter: string
  distance: number
  x: number
  y: number
  angle: number
}

/**
 * Two laps on one distance axis, as stacked panels sharing the crosshair: speed (with corner numbers), the time gap,
 * throttle, brake and gear. One chart per channel keeps each on its own scale (never two y-axes on one chart).
 */
export function telemetryOption(laps: TelemetryLap[], delta: number[] | undefined, corners: Corner[], colors: string[]): EChartsOption {
  const panels = [
    { key: 'speed', label: 'Speed (km/h)', height: 34 },
    { key: 'delta', label: 'Gap (s)', height: 14 },
    { key: 'throttle', label: 'Throttle (%)', height: 14 },
    { key: 'brake', label: 'Brake', height: 8 },
    { key: 'gear', label: 'Gear', height: 12 },
  ].filter((p) => p.key !== 'delta' || (delta && laps.length === 2))
  const top0 = 4
  const gap = 3.2
  let top = top0
  const grids = panels.map((p) => {
    const g = { left: 52, right: 16, top: `${top}%`, height: `${p.height}%` }
    top += p.height + gap
    return g
  })
  const maxD = Math.max(...laps.map((l) => l.distance[l.distance.length - 1] ?? 0))
  const xAxes = panels.map((_, i) => ({
    type: 'value' as const,
    gridIndex: i,
    min: 0,
    max: maxD,
    axisLabel: { show: i === panels.length - 1, formatter: (v: number) => `${(v / 1000).toFixed(1)} km` },
    splitLine: { show: false },
    axisPointer: { show: true },
  }))
  const yAxes = panels.map((p, i) => ({
    type: 'value' as const,
    gridIndex: i,
    name: p.label,
    nameLocation: 'middle' as const,
    nameGap: 38,
    nameTextStyle: { fontSize: 10 },
    scale: p.key === 'speed',
    min: p.key === 'brake' ? 0 : p.key === 'throttle' ? 0 : undefined,
    max: p.key === 'brake' ? 1 : p.key === 'throttle' ? 100 : undefined,
    interval: p.key === 'brake' ? 1 : undefined,
    splitNumber: p.key === 'speed' ? 4 : 2,
    axisLabel: { fontSize: 10, formatter: p.key === 'brake' ? (v: number) => (v ? 'On' : '') : undefined },
  }))
  const series: SeriesOption[] = []
  const seriesPanel: string[] = []
  panels.forEach((p, gi) => {
    if (p.key === 'delta') {
      seriesPanel.push('delta')
      const base = laps[0]!
      series.push({
        name: `Gap of ${laps[1]!.abbreviation ?? laps[1]!.name}`,
        type: 'line',
        xAxisIndex: gi,
        yAxisIndex: gi,
        showSymbol: false,
        color: colors[1],
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.1 },
        data: base.distance.map((d, i) => [d, delta![i]]),
        markLine: { silent: true, symbol: 'none', lineStyle: { color: cssVar('--axis'), type: 'solid' }, label: { show: false }, data: [{ yAxis: 0 }] },
      } as SeriesOption)
      return
    }
    laps.forEach((lap, li) => {
      const values = lap[p.key as 'speed' | 'throttle' | 'brake' | 'gear']
      seriesPanel.push(p.key)
      series.push({
        name: lap.abbreviation ?? lap.name,
        type: 'line',
        xAxisIndex: gi,
        yAxisIndex: gi,
        showSymbol: false,
        step: p.key === 'gear' || p.key === 'brake' ? 'end' : undefined,
        color: colors[li],
        lineStyle: { width: p.key === 'speed' ? 2 : 1.5 },
        data: lap.distance.map((d, i) => [d, values[i]]),
        ...(p.key === 'speed' && li === 0 && corners.length
          ? {
              markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: { color: cssVar('--grid'), type: 'solid', width: 1 },
                label: { formatter: '{b}', position: 'start', color: cssVar('--muted'), fontSize: 10 },
                data: corners.map((c) => ({ xAxis: c.distance, name: `${c.number}${c.letter}` })),
              },
            }
          : {}),
      } as SeriesOption)
    })
  })
  return {
    animation: false,
    legend: { top: 0, right: 0, data: laps.map((l) => l.abbreviation ?? l.name) },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params: unknown) => {
        const list = params as (Tip & { axisValue: number; seriesIndex: number })[]
        if (!list.length) return ''
        const d = (list[0]!.value as number[])[0]!
        const rows = new Map<string, string[]>()
        for (const p of list) {
          const v = (p.value as number[])[1]
          const label = p.seriesName.startsWith('Gap of') ? 'Gap' : p.seriesName
          const panel = seriesPanel[p.seriesIndex]
          const text =
            panel === 'speed' ? `${Math.round(v!)} km/h` : panel === 'throttle' ? `${Math.round(v!)}%` : panel === 'brake' ? (v ? 'brake' : '–') : panel === 'gear' ? `gear ${v}` : `${v! > 0 ? '+' : ''}${v!.toFixed(3)}s`
          if (!rows.has(label)) rows.set(label, [])
          rows.get(label)!.push(text)
        }
        return (
          `<div style="font-weight:600;margin-bottom:4px">${(d / 1000).toFixed(2)} km</div>` +
          [...rows.entries()].map(([k, v]) => `<div><b>${esc(k)}</b> ${v.join(' · ')}</div>`).join('')
        )
      },
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
  }
}

/** Gap to the fastest car, race by race, one line per team (team colours, dashed when two teams share a colour). */
export function competitiveOrderOption(
  data: { rounds: { round: number; abbreviation: string }[]; teams: { id: string; name: string; gaps: (number | null)[] }[] },
  limit = 10,
): EChartsOption {
  const teams = data.teams.slice(0, limit)
  const seen = new Map<string, number>()
  return {
    animation: false,
    legend: { type: 'scroll', top: 0, left: 0, right: 0 },
    grid: { left: 8, right: 64, top: 40, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = (params as (Tip & { dataIndex: number })[]).filter((p) => p.value != null).sort((a, b) => (a.value as number) - (b.value as number))
        const r = data.rounds[list[0]?.dataIndex ?? 0]
        return (
          `<div style="font-weight:600;margin-bottom:4px">Round ${r?.round} · ${esc(r?.abbreviation ?? '')}</div>` +
          list.map((p) => `<div>${key(p.color)}<b style="display:inline-block;min-width:56px">${(p.value as number) === 0 ? 'fastest' : `+${(p.value as number).toFixed(2)}%`}</b>${esc(p.seriesName)}</div>`).join('')
        )
      },
    },
    xAxis: { type: 'category', data: data.rounds.map((r) => r.abbreviation), boundaryGap: false },
    yAxis: { type: 'value', inverse: true, min: 0, axisLabel: { formatter: (v: number) => (v === 0 ? 'Fastest' : `+${v}%`) } },
    series: teams.map((t) => {
      const color = teamColor(t.id)
      const n = (seen.get(color) ?? 0) + 1
      seen.set(color, n)
      return {
        name: t.name,
        type: 'line',
        data: t.gaps,
        color,
        connectNulls: true,
        symbolSize: 6,
        lineStyle: { width: 2, type: n > 1 ? [5, 3] : 'solid' },
        endLabel: { show: true, formatter: '{a}', color: cssVar('--ink-2'), fontSize: 11, fontWeight: 600 },
        emphasis: { focus: 'series' },
      } as SeriesOption
    }),
  }
}
