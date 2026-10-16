import { fileURLToPath } from 'node:url'

// Движок сайтов: API, формы, блог и страницы на Nuxt UI. Сайт подключает его одной строкой:
//   extends: [['gh:mcnickbronx/web-start/front#v1.0.0', { install: true }]]
// Своё у сайта — в его app/: файл с тем же именем, что в движке, перекрывает движок
export default defineNuxtConfig({
  compatibilityDate: '2026-09-01',
  devtools: { enabled: false },
  extends: ['./layers/core', './layers/form', './layers/page'],
  modules: ['@nuxt/ui'],
  css: [fileURLToPath(new URL('./app/assets/css/main.css', import.meta.url))],
})
