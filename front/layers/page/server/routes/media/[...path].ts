// Картинки из админки: адреса в статьях — /media/… от корня сайта, а лежат они на бэкенде.
// На сервере быстрее отдать /media прокси (Traefik) прямо в контейнер файлов бэкенда, минуя Node
export default defineEventHandler((event) => {
  assertMethod(event, 'GET', true) // только чтение: картинки не загружают через сайт
  const url = mediaUrl(event.path, useRuntimeConfig(event).public.apiBase)
  if (!url) {
    throw createError({ statusCode: 404 })
  }
  return proxyRequest(event, url, { fetchOptions: { signal: AbortSignal.timeout(60_000) } })
})
