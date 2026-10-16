export interface SitemapEntry {
  /** Адрес от корня сайта: /blog, /novosti/statya */
  loc: string
  /** Дата изменения, ISO */
  lastmod?: string
}

const XML_ESCAPE_MAP: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&apos;' }

/** sitemap.xml: абсолютные адреса от origin, дата изменения — только день. Один адрес — одна запись,
 * первая: страница фронта и страница из админки с тем же адресом — это страница фронта */
export function buildSitemapXml(origin: string, entryList: SitemapEntry[]): string {
  const locSet = new Set<string>()
  const urlList = entryList.filter(entry => !locSet.has(entry.loc) && locSet.add(entry.loc)).map((entry) => {
    const loc = new URL(entry.loc, origin).href.replace(/[&<>"']/g, char => XML_ESCAPE_MAP[char]!)
    const lastmod = entry.lastmod ? `<lastmod>${entry.lastmod.slice(0, 10)}</lastmod>` : ''
    return `  <url><loc>${loc}</loc>${lastmod}</url>`
  })
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urlList.join('\n')}\n</urlset>\n`
}
