// Ответы API страниц с кэшем на сервере сайта. Одновременные запросы одного адреса бэкенд получает
// одним запросом; бэкенд не ответил — посетители получают последнее сохранённое.
// Правила кэша — page-cache.ts
export const fetchPageApi = defineCachedFunction(async (url: string) => {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(60_000) })
    return { status: response.status, body: await response.text() }
  }
  catch {
    return { status: 502, body: JSON.stringify({ message: 'Сервер не ответил' }) }
  }
}, {
  name: 'page-api',
  // Своё хранилище с пределом числа записей — nuxt.config.ts слоя
  base: 'page-api',
  swr: true,
  maxAge: PAGE_CACHE_SECONDS,
  validate: entry => !!entry.value && isPageResponseCacheable(entry.value.status),
})
