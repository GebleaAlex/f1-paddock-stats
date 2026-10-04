import { describe, expect, it } from 'vitest'
import { compound, labelled, neutralBands, withLapMarks } from '../app/utils/charts'

describe('race analysis helpers', () => {
  it('knows the tyre compounds and falls back for unknown ones', () => {
    expect(compound('SOFT').short).toBe('S')
    expect(compound(null).label).toBe('Unknown')
  })
  it('keeps end labels that do not collide', () => {
    const keep = labelled({ a: 100, b: 99, c: 80, d: 79.5, e: undefined }, 5)
    expect([...keep].sort()).toEqual(['a', 'c'])
  })
  it('turns safety-car periods into shaded lap ranges', () => {
    const bands = neutralBands([{ kind: 'sc', label: 'Safety car', from_lap: 3, to_lap: 5 }])
    expect(bands?.data[0]?.[0]?.xAxis).toBe(2.5)
    expect(bands?.data[0]?.[1]?.xAxis).toBe(5.5)
    expect(neutralBands([])).toBeUndefined()
  })
  it('marks a lap on the first series only', () => {
    const option = withLapMarks({ series: [{ type: 'line', data: [] }, { type: 'line', data: [] }] }, [], 12) as {
      series: { markLine?: { data: { xAxis: number }[] } }[]
    }
    expect(option.series[0]!.markLine!.data[0]!.xAxis).toBe(12)
    expect(option.series[1]!.markLine).toBeUndefined()
  })
})
