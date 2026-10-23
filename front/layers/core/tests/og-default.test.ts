import { describe, expect, it } from 'vitest'
import { ogDefault } from '../app/utils/og-default'

describe('ogDefault', () => {
  it('без настройки — тегов нет', () => {
    const meta = ogDefault('https://example.com', { siteName: '', image: '' })
    expect(meta.ogSiteName).toBeUndefined()
    expect(meta.ogImage).toBeUndefined()
  })

  it('картинка из public/ — полным адресом от адреса сайта', () => {
    const meta = ogDefault('https://example.com', { siteName: 'Пример', image: '/images/og.png' })
    expect(meta).toEqual({ ogSiteName: 'Пример', ogImage: 'https://example.com/images/og.png' })
    expect(ogDefault('https://example.com/sub/', { siteName: '', image: '/og.png' }).ogImage).toBe('https://example.com/og.png')
    expect(ogDefault('http://localhost:3000', { siteName: '', image: '/og.png' }).ogImage).toBe('http://localhost:3000/og.png')
  })

  it('полный адрес картинки остаётся как есть', () => {
    expect(ogDefault('https://example.com', { siteName: '', image: 'https://cdn.example.com/og.png' }).ogImage)
      .toBe('https://cdn.example.com/og.png')
  })
})
