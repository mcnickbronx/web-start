import { describe, expect, it } from 'vitest'
import { isPageResponseCacheable, pageApiUrl } from '../server/utils/page-cache'

describe('isPageResponseCacheable', () => {
  it('ответ о странице — в кэш, есть она или нет: снятая с публикации статья уходит с сайта', () => {
    expect(isPageResponseCacheable(200)).toBe(true)
    expect(isPageResponseCacheable(404)).toBe(true)
  })

  it('сбой — мимо кэша: посетители получают последнее сохранённое', () => {
    for (const status of [429, 500, 502, 503, 504]) {
      expect(isPageResponseCacheable(status)).toBe(false)
    }
  })
})

describe('pageApiUrl', () => {
  const apiBase = 'https://back.example.ru'

  it('путь слоя — в /api/page/ с параметрами', () => {
    expect(pageApiUrl('/_page-api/list?page=2&row=12', apiBase)).toBe('https://back.example.ru/api/page/list?page=2&row=12')
    expect(pageApiUrl('/_page-api/detail/o-kompanii', apiBase)).toBe('https://back.example.ru/api/page/detail/o-kompanii')
    expect(pageApiUrl('/_page-api/redirect?path=%2Fnews%2F1.html', apiBase)).toBe('https://back.example.ru/api/page/redirect?path=%2Fnews%2F1.html')
  })

  it('лишние параметры отбрасываются, остальные — в одном порядке: один адрес — одна запись в кэше', () => {
    expect(pageApiUrl('/_page-api/list?row=12&x=1&page=2&utm_source=vk', apiBase)).toBe('https://back.example.ru/api/page/list?page=2&row=12')
    expect(pageApiUrl('/_page-api/detail/o-kompanii?nocache=123', apiBase)).toBe('https://back.example.ru/api/page/detail/o-kompanii')
    expect(pageApiUrl('/_page-api/list?search=&sort=-title&category_slug=novosti', apiBase)).toBe('https://back.example.ru/api/page/list?category_slug=novosti&sort=-title')
  })

  it('выход из /api/page/ — отказ: иначе через кэш можно было бы достать другое API', () => {
    expect(pageApiUrl('/_page-api/../user/me', apiBase)).toBeNull()
    expect(pageApiUrl('/_page-api/%2e%2e/form/detail/callback', apiBase)).toBeNull()
    expect(pageApiUrl('/_page-api/%2E%2E/%2E%2E/admin/', apiBase)).toBeNull()
  })
})
