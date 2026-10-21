import { describe, expect, it } from 'vitest'
import { canonicalUrl } from '../app/utils/canonical-url'

describe('canonicalUrl', () => {
  it('метки рекламы — та же страница', () => {
    expect(canonicalUrl('https://example.com', '/?utm_source=ya&yclid=1')).toBe('https://example.com/')
    expect(canonicalUrl('https://example.com', '/novosti/x?utm_source=x#top')).toBe('https://example.com/novosti/x')
  })

  it('хвост и путь в адресе сайта отбрасываются', () => {
    expect(canonicalUrl('https://example.com/', '/novosti/x')).toBe('https://example.com/novosti/x')
    expect(canonicalUrl('https://example.com/sub', '/novosti/x')).toBe('https://example.com/novosti/x')
  })

  it('путь, похожий на чужой домен, остаётся на сайте', () => {
    expect(new URL(canonicalUrl('https://example.com', '//evil.example/x')).host).toBe('example.com')
    expect(new URL(canonicalUrl('https://example.com', '/\\evil.example')).host).toBe('example.com')
  })

  it('порт адреса сайта на месте', () => {
    expect(canonicalUrl('http://localhost:3000', '/login')).toBe('http://localhost:3000/login')
  })
})
