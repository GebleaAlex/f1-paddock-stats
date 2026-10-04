import { describe, expect, it } from 'vitest'
import { cumulative, gapChartOption } from '../app/utils/charts'
import { driverStyles, teamColor } from '../app/utils/teams'
import type { RaceLaps } from '../app/utils/types'

const entry = (driver_id: string, constructor_id: string) => ({
  driver_id, driver: driver_id, abbreviation: driver_id.slice(0, 3).toUpperCase(), driver_number: null,
  constructor_id, constructor: constructor_id, engine_manufacturer_id: null, engine: null,
  position: 1, position_text: '1', grid: 1, laps: 3, reason_retired: null,
})

const race: RaceLaps = {
  race: { id: 1, year: 2021, round: 1, grand_prix: 'Test', laps: 3, date: '2021-01-01' },
  drivers: [entry('aaa', 'mclaren'), entry('bbb', 'mclaren'), entry('ccc', 'ferrari')],
  laps: {
    aaa: [[1, 1, 90000], [2, 1, 90000], [3, 2, 92000]],
    bbb: [[1, 2, 91000], [2, 2, 90000], [3, 1, 90000]],
    ccc: [[1, 3, 95000]],
  },
  pit_stops: [],
}

describe('teams', () => {
  it('dashes the second driver of a team', () => {
    const s = driverStyles(race.drivers)
    expect(s.aaa).toEqual({ color: teamColor('mclaren'), dashed: false })
    expect(s.bbb!.dashed).toBe(true)
    expect(s.ccc!.dashed).toBe(false)
  })
  it('gives unknown teams a stable fallback colour', () => {
    expect(teamColor('made-up-team')).toBe(teamColor('made-up-team'))
  })
})

describe('race maths', () => {
  it('accumulates race time per lap', () => {
    expect(cumulative(race).bbb).toEqual([undefined, 91000, 181000, 271000])
  })
  it('measures gaps to whoever led each lap', () => {
    const option = gapChartOption(race, 'leader') as { series: { id: string; data: { value: [number, number] }[] }[] }
    const bbb = option.series.find((s) => s.id === 'bbb')!
    expect(bbb.data.map((d) => d.value)).toEqual([[1, 1], [2, 1], [3, 0]])
  })
})
