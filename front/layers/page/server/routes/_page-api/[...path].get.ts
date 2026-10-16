// Данные страниц для рендера на сервере сайта — через кэш слоя: страницу, которую открыли сто человек,
// сервер берёт у бэкенда раз в минуту, а не сто раз. Только GET и только /api/page/…: формы, вход
// и кабинет сюда не попадают. usePageApi() зовёт маршрут внутри процесса Nuxt — без сети и лимитов Traefik
export default defineEventHandler(async (event) => {
  const url = pageApiUrl(event.path, useRuntimeConfig(event).public.apiBase)
  if (!url) {
    throw createError({ statusCode: 404 })
  }
  const { status, body } = await fetchPageApi(url)
  setResponseStatus(event, status)
  setResponseHeader(event, 'content-type', 'application/json')
  return body
})
