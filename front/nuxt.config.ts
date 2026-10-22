import { fileURLToPath } from 'node:url'

// Движок сайтов: API, формы, блог и страницы на Nuxt UI. Сайт подключает его одной строкой:
//   extends: [['gh:mcnickbronx/web-start/front#v2.4.0', { install: true }]]
// Своё у сайта — в его app/: файл с тем же именем, что в движке, перекрывает движок
export default defineNuxtConfig({
  compatibilityDate: '2026-09-01',
  devtools: { enabled: false },
  // user — слой кабинета, в движок сайтов не входит: сайт с кабинетом добавляет его второй строкой extends,
  // тег тот же, без install — 'gh:mcnickbronx/web-start/front/layers/user#v2.4.0' (layers/user/readme.md)
  extends: ['./layers/core', './layers/form', './layers/page'],
  modules: ['@nuxt/ui'],
  css: [fileURLToPath(new URL('./app/assets/css/main.css', import.meta.url))],
})
