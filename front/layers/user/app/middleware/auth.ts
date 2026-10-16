/**
 * Страница только для вошедших: definePageMeta({ middleware: 'auth' }).
 * Нет токена — пробуем обновить по куке, не вышло — на вход, с возвратом обратно.
 *
 * Токен живёт только в браузере, поэтому кабинет (/lk/**) рендерится только в браузере —
 * так задано в nuxt.config.ts слоя.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) {
    return
  }
  const access = useAccessToken()
  if (!access.value) {
    await useNuxtApp()._refreshAccess?.()
  }
  if (!access.value) {
    return navigateTo({ path: '/login', query: { next: to.fullPath } })
  }
})
