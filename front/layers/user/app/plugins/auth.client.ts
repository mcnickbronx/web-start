/**
 * Обновление access-токена по refresh из куки бэкенда. Подключается к клиенту core: тот вызывает
 * его на 401, middleware auth — при входе в кабинет. Одновременные запросы делят одно обновление.
 */
export default defineNuxtPlugin((nuxtApp) => {
  const access = useAccessToken()
  const { apiBase } = useRuntimeConfig().public
  let pending: Promise<string | null> | null = null

  nuxtApp._refreshAccess = () => {
    // Мимо useApi(): тот на 401 сам зовёт обновление — запрос ждал бы сам себя
    pending ??= $fetch<{ access: string }>('/api/user/refresh', { baseURL: apiBase, method: 'POST', credentials: 'include', timeout: 60_000 })
      .then(result => (access.value = result.access))
      .catch(() => (access.value = null))
      .finally(() => (pending = null))
    return pending
  }
})
