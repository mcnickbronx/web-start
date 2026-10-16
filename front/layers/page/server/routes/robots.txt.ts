// robots.txt: открыт сайт для поиска или закрыт — NUXT_PUBLIC_SITE_INDEXED. Свой файл целиком —
// public/robots.txt сайта: статика отдаётся раньше этого маршрута
export default defineEventHandler((event) => {
  const { siteIndexed, siteUrl } = useRuntimeConfig(event).public
  setHeader(event, 'content-type', 'text/plain; charset=utf-8')
  return buildRobotsTxt(Boolean(siteIndexed), siteUrl || getRequestURL(event).origin)
})
