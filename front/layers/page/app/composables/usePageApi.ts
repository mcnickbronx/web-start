import createClient from 'openapi-fetch'
import type { components, paths } from '#api-types'

/** Лента статей — ответ /api/page/list. Этим типом ленту берут компоненты, которые сайт перекрывает
 * (PageBlog, PageFeed): имя схемы в API может смениться, а этот тип останется */
export type PageFeedList = components['schemas']['ListOut_PageListOut_']

/**
 * Клиент API для данных страниц. При рендере на сервере сайта — через кэш слоя (/_page-api, внутри
 * процесса Nuxt): все посетители иначе ходили бы к API с одного адреса сервера и делили бы
 * его лимит в Traefik. В браузере — прямо в API, как useApi(). Вызовы и типы — те же:
 *
 *   const { data, error } = await apiRequest(usePageApi().GET('/api/page/list'))
 *
 * Данные для страницы сайта — через usePageRequest(): он берёт этот клиент сам.
 */
export function usePageApi() {
  const event = useRequestEvent()
  if (import.meta.client || !event) {
    return useApi()
  }
  return createClient<paths>({
    baseUrl: useRuntimeConfig().public.apiBase,
    fetch: (request: Request) => {
      const url = new URL(request.url)
      return event.fetch(url.pathname.replace(/^\/api\/page\//, '/_page-api/') + url.search)
    },
  })
}
