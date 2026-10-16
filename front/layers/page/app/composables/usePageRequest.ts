/**
 * Данные публичной страницы: запрос через usePageApi() — при серверном рендере через кэш слоя,
 * ошибка API — страница ошибки с тем же кодом (404 — «не найдено»). Пустую страницу с кодом 200
 * поисковик проиндексировал бы как настоящую.
 *
 *   const page = await usePageRequest(`page-${slug}`, api => api.GET('/api/page/detail/{slug}', …))
 */
export async function usePageRequest<T>(
  key: string,
  request: (api: ReturnType<typeof usePageApi>) => Promise<{ data?: T, error?: unknown, response: Response }>,
): Promise<T> {
  const api = usePageApi()
  const { data } = await useAsyncData(key, () => apiRequest(request(api)))
  const result = data.value
  if (!result || result.error) {
    throw createError({ statusCode: result?.error.status || 502, message: result?.error.message, fatal: true })
  }
  return result.data
}
