import { describe, expect, it } from 'vitest'
import { parsePageNumber } from '../app/utils/page-number'

describe('parsePageNumber', () => {
  it('число из адреса', () => {
    expect(parsePageNumber('3')).toBe(3)
    expect(parsePageNumber(['2', '5'])).toBe(2)
  })
  it('без номера и с мусором — первая страница', () => {
    for (const value of [undefined, '', 'abc', '0', '-2', '1.5', null]) {
      expect(parsePageNumber(value)).toBe(1)
    }
  })
})
