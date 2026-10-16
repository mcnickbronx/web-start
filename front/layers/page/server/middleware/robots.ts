// Закрытый сайт — X-Robots-Tag на все ответы. robots.txt только просит не обходить сайт, а уже
// найденные страницы поисковик убирает из выдачи по noindex
export default defineEventHandler((event) => {
  if (!useRuntimeConfig(event).public.siteIndexed) {
    setHeader(event, 'X-Robots-Tag', 'noindex, nofollow')
  }
})
