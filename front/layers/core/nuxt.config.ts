import { fileURLToPath } from 'node:url'

// Слой core: связь с API бэкенда — клиент с типами из openapi.json и разбор ошибок.
// От него зависят остальные слои, сам он не зависит ни от кого
export default defineNuxtConfig({
  // Типы API для других слоёв и сайта: import type { components } from '#api-types'.
  // Свой псевдоним, а не #layers/core: тот есть, только пока слой лежит в папке layers/ проекта
  alias: { '#api-types': fileURLToPath(new URL('./app/types/api', import.meta.url)) },
  runtimeConfig: {
    public: {
      // Адрес бэкенда. Переопределяется в .env: NUXT_PUBLIC_API_BASE
      apiBase: 'http://localhost:8000',
      // Номер счётчика Яндекс Метрики: NUXT_PUBLIC_METRIKA_ID. Пусто — счётчика нет
      metrikaId: '',
      // Адрес сайта для canonical, Open Graph и sitemap.xml. Переопределяется в .env: NUXT_PUBLIC_SITE_URL.
      // Пусто — берётся из запроса (годится для разработки: за прокси протокол может оказаться http)
      siteUrl: '',
    },
  },
})
