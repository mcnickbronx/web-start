import { describe, expect, it } from 'vitest'
import { buildSitemapXml } from '../server/utils/sitemap'

describe('buildSitemapXml', () => {
  it('абсолютные адреса и дата изменения — день', () => {
    const xml = buildSitemapXml('https://site.ru', [{ loc: '/' }, { loc: '/novosti/statya', lastmod: '2026-09-29T10:15:00+03:00' }])
    expect(xml).toContain('<url><loc>https://site.ru/</loc></url>')
    expect(xml).toContain('<url><loc>https://site.ru/novosti/statya</loc><lastmod>2026-09-29</lastmod></url>')
    expect(xml.startsWith('<?xml')).toBe(true)
  })
  it('экранирует спецсимволы XML', () => {
    expect(buildSitemapXml('https://site.ru', [{ loc: '/poisk?a=1&b=2' }])).toContain('https://site.ru/poisk?a=1&amp;b=2')
  })
  it('один адрес — одна запись, первая: страница фронта важнее страницы из админки', () => {
    const xml = buildSitemapXml('https://site.ru', [{ loc: '/uslugi' }, { loc: '/blog' }, { loc: '/uslugi', lastmod: '2026-09-29' }])
    expect(xml.match(/uslugi/g)).toHaveLength(1)
    expect(xml).toContain('<url><loc>https://site.ru/uslugi</loc></url>')
    expect(xml.indexOf('uslugi')).toBeLessThan(xml.indexOf('blog'))
  })
  it('адрес сайта со слешем на конце не даёт двойного слеша', () => {
    expect(buildSitemapXml('https://site.ru/', [{ loc: '/blog' }])).toContain('<loc>https://site.ru/blog</loc>')
  })
})
