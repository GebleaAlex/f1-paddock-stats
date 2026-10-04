import { describe, expect, it } from 'vitest'
import { age, gapSeconds, lapTime, listing, ordinal, pct, points, years } from '../app/utils/format'

describe('format', () => {
  it('formats lap times', () => {
    expect(lapTime(76290)).toBe('1:16.290')
    expect(lapTime(59999)).toBe('59.999')
    expect(lapTime(8003600)).toBe('2:13:23.600')
    expect(lapTime(null)).toBe('–')
  })
  it('signs gaps and percentages', () => {
    expect(gapSeconds(1234)).toBe('+1.234s')
    expect(gapSeconds(-500, 1)).toBe('−0.5s')
    expect(pct(-0.109)).toBe('−0.109%')
    expect(pct(0.2, 1)).toBe('+0.2%')
  })
  it('writes ordinals', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 101].map(ordinal)).toEqual([
      '1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '101st',
    ])
  })
  it('keeps half points', () => {
    expect(points(395.5)).toBe('395.5')
    expect(points(25)).toBe('25')
  })
  it('computes ages on the right side of the birthday', () => {
    expect(age('1997-09-30', '2015-03-15')).toBe(17)
    expect(age('1997-09-30', '2016-09-30')).toBe(19)
  })
  it('joins lists and year ranges', () => {
    expect(listing(['McLaren', 'Mercedes', 'Ferrari'])).toBe('McLaren, Mercedes and Ferrari')
    expect(years(2007, 2007)).toBe('2007')
    expect(years(2007, 2026)).toBe('2007–2026')
  })
})
