import { describe, expect, it } from 'vitest'
import { formatPageDate } from '../app/utils/format-date'

describe('formatPageDate', () => {
  it('дата по Москве, а не по поясу машины', () => {
    // 22:30 UTC 28 сентября — в Москве уже 29-е
    expect(formatPageDate('2026-09-28T22:30:00Z')).toBe('29 сентября 2026 г.')
  })
})
