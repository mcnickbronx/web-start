// Старые адреса. По адресу ничего нет — сервер сайта спрашивает бэкенд, не переехала ли страница
// (админка → «Редиректы», туда же сам записывается старый адрес при смене слага), и отвечает
// постоянным редиректом с теми же параметрами: метки рекламы доходят до заявки.
// Плагин работает, когда сервер рисует страницу 404: Nuxt рисует её отдельным проходом, и ошибка
// известна с самого начала. Живые страницы лишнего запроса не делают. Переход по ссылке внутри сайта
// идёт в браузере и сюда не попадает — только открытие адреса: поисковик, закладка, ссылка извне
export default defineNuxtPlugin(async (nuxtApp) => {
  if (useError().value?.statusCode !== 404) {
    return
  }
  const { pathname, search } = new URL(nuxtApp.ssrContext!.url, 'http://localhost')
  const { data } = await apiRequest(usePageApi().GET('/api/page/redirect', { params: { query: { path: pathname } } }))
  if (data) {
    await navigateTo(data.path_to + search, { redirectCode: 301 })
  }
})
