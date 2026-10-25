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

  it('номер страницы ленты — в адресе, со второй', () => {
    expect(canonicalUrl('https://example.com', '/blog', 2)).toBe('https://example.com/blog?page=2')
    expect(canonicalUrl('https://example.com', '/blog', 1)).toBe('https://example.com/blog')
    expect(canonicalUrl('https://example.com', '/blog', 2.5)).toBe('https://example.com/blog')
    expect(canonicalUrl('https://example.com', '/blog?utm_source=x&page=7', 3)).toBe('https://example.com/blog?page=3')
    expect(new URL(canonicalUrl('https://example.com', '//evil.example/x', 2)).host).toBe('example.com')
  })
})
