import { describe, expect, it } from 'vitest'
import { mediaUrl } from '../server/utils/media'

describe('mediaUrl', () => {
  const apiBase = 'https://back.example.ru'

  it('картинка — в /media/ бэкенда', () => {
    expect(mediaUrl('/media/page/2026/09/a.webp', apiBase)).toBe('https://back.example.ru/media/page/2026/09/a.webp')
  })

  it('выход из /media/ — отказ: иначе сайт стал бы прокси к API и админке бэкенда', () => {
    expect(mediaUrl('/media/../admin/login/', apiBase)).toBeNull()
    expect(mediaUrl('/media/%2e%2e/api/user/me', apiBase)).toBeNull()
    expect(mediaUrl('/media/%2E%2E/%2E%2E/api/health', apiBase)).toBeNull()
    expect(mediaUrl('/media/..\\api/user/me', apiBase)).toBeNull()
  })
})
