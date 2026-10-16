import { describe, expect, it } from 'vitest'
import { buildRobotsTxt } from '../server/utils/robots'

describe('buildRobotsTxt', () => {
  it('закрытый сайт — запрет целиком, без карты сайта', () => {
    expect(buildRobotsTxt(false, 'https://site.ru')).toBe('User-agent: *\nDisallow: /\n')
  })

  it('открытый — служебное закрыто, скрипты открыты, метки склеены, карта сайта', () => {
    const text = buildRobotsTxt(true, 'https://site.ru')
    expect(text).toContain('Disallow: /_page-api/')
    expect(text).not.toContain('Disallow: /\n')
    expect(text).not.toContain('/_nuxt')
    expect(text).toContain('Clean-param: utm_source&')
    expect(text).toContain('Sitemap: https://site.ru/sitemap.xml')
  })
})
