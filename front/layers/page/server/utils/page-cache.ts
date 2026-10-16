// Правила кэша API страниц: сколько ответ свежий, какие ответы сохранять, какие адреса пускать.
// Чистые функции с тестами; сам кэш — page-api.ts

/** Сколько ответ API страниц считается свежим на сервере сайта, секунд. Потом посетитель
 * всё равно сразу получает сохранённое, а свежее сервер берёт у бэкенда в фоне */
export const PAGE_CACHE_SECONDS = 60

/**
 * Можно ли сохранить ответ API страниц. Ответ о самой странице — есть она (200) или нет (404) —
 * да: только сохранённый 404 заменит в кэше снятую с публикации статью, иначе она жила бы на сайте
 * вечно. Сбой — лимит Traefik (429), ошибка или молчание бэкенда (5xx) — нет: посетители получают
 * последнее сохранённое, пока бэкенд не ответит.
 */
export function isPageResponseCacheable(status: number): boolean {
  return status === 200 || status === 404
}

/** Параметры API страниц. Остальные бэкенд всё равно не читает — их отбрасываем: иначе мусорные
 * параметры (?x=1, ?x=2…) плодили бы записи в кэше и каждый раз ходили бы мимо него к бэкенду */
const PAGE_API_PARAM_LIST = ['category_slug', 'page', 'path', 'row', 'search', 'sort']

/** Адрес в API для пути вида /_page-api/list?page=2 — или null, если путь уводит из /api/page/ */
export function pageApiUrl(path: string, apiBase: string): string | null {
  const url = new URL(path.replace(/^\/_page-api\//, '/api/page/'), apiBase)
  if (!url.pathname.startsWith('/api/page/')) {
    return null
  }
  const query = new URLSearchParams()
  for (const name of PAGE_API_PARAM_LIST) {
    const value = url.searchParams.get(name)
    if (value) {
      query.set(name, value)
    }
  }
  url.search = query.toString()
  return url.href
}
