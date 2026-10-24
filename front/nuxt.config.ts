import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readDependencies, versionDiff } from './layers/core/version-guard'

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
  hooks: {
    // Забытое при обновлении движка — версии nuxt, vue, vue-router в package.json сайта — иначе проходит молча.
    // Сравниваются объявленные версии сайта и движка, без сети; только предупреждение, сборка не падает
    ready(nuxt) {
      try {
        const differ = versionDiff(
          readDependencies(fileURLToPath(new URL('./package.json', import.meta.url))),
          readDependencies(join(nuxt.options.rootDir, 'package.json')),
        )
        if (differ.length) {
          console.warn(`[web-start] версии в package.json сайта не как у движка: ${differ.join(', ')} — поменять и npm install (front/readme.md, «Обновить движок»)`)
        }
      }
      catch { /* подсказка не должна ронять сборку сайта */ }
    },
  },
  css: [fileURLToPath(new URL('./app/assets/css/main.css', import.meta.url))],
})
