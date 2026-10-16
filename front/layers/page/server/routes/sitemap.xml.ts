// sitemap.xml: страницы фронта (page.sitemapPageList в app.config сайта) и адреса из админки.
// Бэкенд не ответил — отдаём хотя бы страницы фронта: пустая карта хуже для поисковика, чем неполная
export default defineEventHandler(async (event) => {
  const { apiBase, siteUrl } = useRuntimeConfig(event).public
  let backendList: SitemapEntry[] = []
  // Через кэш слоя, как данные страниц: поисковики и боты запрашивают карту часто
  const { status, body } = await fetchPageApi(new URL('/api/page/sitemap', apiBase).href)
  if (status === 200) {
    backendList = (JSON.parse(body) as { items: SitemapEntry[] }).items
  }
  else {
    console.warn(`sitemap.xml: бэкенд ответил ${status}, в карте только страницы фронта`)
  }
  setHeader(event, 'content-type', 'application/xml; charset=utf-8')
  const frontList = useAppConfig().page.sitemapPageList.map((loc: string) => ({ loc }))
  return buildSitemapXml(siteUrl || getRequestURL(event).origin, [...frontList, ...backendList])
})
