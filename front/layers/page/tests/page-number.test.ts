import { describe, expect, it } from 'vitest'
import { feedPath, parsePageNumber } from '../app/utils/page-number'

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

describe('feedPath', () => {
  it('первая страница — без номера, остальные — с ним', () => {
    expect(feedPath('/blog', 1)).toBe('/blog')
    expect(feedPath('/novosti', 3)).toBe('/novosti?page=3')
  })
})
