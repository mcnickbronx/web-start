import { describe, expect, it } from 'vitest'
import { buildVisit, readYmClientId, shouldReplaceVisit, VISIT_TTL_MS } from '../app/utils/visit'

describe('buildVisit', () => {
  it('чужой сайт — источник, страница с метками целиком', () => {
    expect(buildVisit('https://yandex.ru/search/?text=медосмотр', '/uslugi?utm_source=yandex', 'example.ru'))
      .toEqual({ referrer: 'https://yandex.ru/search/?text=медосмотр', landing_page: '/uslugi?utm_source=yandex' })
  })

  it('свой сайт и пустой referrer — прямой заход', () => {
    expect(buildVisit('https://www.example.ru/blog', '/kontakty', 'example.ru').referrer).toBe('')
    expect(buildVisit('', '/', 'example.ru').referrer).toBe('')
  })
})

describe('shouldReplaceVisit', () => {
  const now = 1_000_000_000_000
  const stored = { date: now - 1000 }
  const direct = { referrer: '', landing_page: '/kontakty' }

  it('нет сохранённого или устарел — пишем', () => {
    expect(shouldReplaceVisit(null, direct, now)).toBe(true)
    expect(shouldReplaceVisit({ date: now - VISIT_TTL_MS - 1 }, direct, now)).toBe(true)
  })

  it('прямой заход не затирает источник', () => {
    expect(shouldReplaceVisit(stored, direct, now)).toBe(false)
  })

  it('новый источник или метки — затирают', () => {
    expect(shouldReplaceVisit(stored, { referrer: 'https://vk.com/', landing_page: '/' }, now)).toBe(true)
    expect(shouldReplaceVisit(stored, { referrer: '', landing_page: '/?yclid=123' }, now)).toBe(true)
  })
})

describe('readYmClientId', () => {
  it('ClientID из куки Метрики', () => {
    expect(readYmClientId('a=1; _ym_uid=1727000000123456789; b=2')).toBe('1727000000123456789')
    expect(readYmClientId('a=1')).toBe('')
  })
})
