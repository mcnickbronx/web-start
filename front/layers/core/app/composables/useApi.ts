import createClient from 'openapi-fetch'
import type { paths } from '../types/api'

declare module '#app' {
  interface NuxtApp {
    /** Обновить access-токен; подключает слой user. Нет слоя — 401 просто возвращается */
    _refreshAccess?: () => Promise<string | null>
  }
}

/** Access-токен пользователя. Живёт только в памяти вкладки, кладёт его слой user. */
export function useAccessToken() {
  return useState<string | null>('core:access', () => null)
}

/**
 * Клиент API бэкенда. Адреса, параметры и ответы типизированы по openapi.json:
 *
 *   const api = useApi()
 *   const { data, error } = await apiRequest(api.GET('/api/page/list', { params: { query: { row: 10 } } }))
 *
 * Access-токен подставляется сам. На 401 клиент один раз обновляет токен и повторяет запрос.
 * Из браузера — с куками бэкенда (credentials: 'include'): refresh-токен слоя user живёт в куке.
 */
export function useApi() {
  const nuxtApp = useNuxtApp()
  const access = useAccessToken()
  const config = useRuntimeConfig()

  // Без таймаута зависший бэкенд подвесит и рендер страницы на сервере Nuxt
  const fetchWithTimeout = (request: Request) => globalThis.fetch(request, { signal: AbortSignal.timeout(60_000) })

  return createClient<paths>({
    baseUrl: config.public.apiBase,
    credentials: 'include',
    fetch: async (request: Request) => {
      const retry = request.clone()
      const token = access.value
      if (token) {
        request.headers.set('Authorization', `Bearer ${token}`)
      }
      const response = await fetchWithTimeout(request)
      if (response.status !== 401 || !token || !nuxtApp._refreshAccess) {
        return response
      }
      const tokenNew = await nuxtApp._refreshAccess()
      if (!tokenNew) {
        return response
      }
      retry.headers.set('Authorization', `Bearer ${tokenNew}`)
      return fetchWithTimeout(retry)
    },
  })
}
