import { describe, expect, it } from 'vitest'
import { canonicalUrl } from '../app/utils/canonical-url'

describe('canonicalUrl', () => {
  it('метки рекламы — та же страница', () => {
    expect(canonicalUrl('https://site.ru', '/?utm_source=ya&yclid=1')).toBe('https://site.ru/')
    expect(canonicalUrl('https://site.ru', '/novosti/x?utm_source=x#top')).toBe('https://site.ru/novosti/x')
  })

  it('хвост и путь в адресе сайта отбрасываются', () => {
    expect(canonicalUrl('https://site.ru/', '/novosti/x')).toBe('https://site.ru/novosti/x')
    expect(canonicalUrl('https://site.ru/sub', '/novosti/x')).toBe('https://site.ru/novosti/x')
  })

  it('путь, похожий на чужой домен, остаётся на сайте', () => {
    expect(new URL(canonicalUrl('https://site.ru', '//evil.com/x')).host).toBe('site.ru')
    expect(new URL(canonicalUrl('https://site.ru', '/\\evil.com')).host).toBe('site.ru')
  })

  it('порт адреса сайта на месте', () => {
    expect(canonicalUrl('http://localhost:3000', '/login')).toBe('http://localhost:3000/login')
  })
})
