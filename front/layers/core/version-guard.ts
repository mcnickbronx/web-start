import { readFileSync } from 'node:fs'

// Сторож версий для сборки сайта (хук в front/nuxt.config.ts). Лежит не в app/, server/, shared/:
// эти папки Nuxt кладёт в приложение, а этот код нужен только при сборке.
// Правило — front/readme.md, «Сайт на движке»: у сайта те же nuxt, vue, vue-router, что у движка.

const GUARDED = ['nuxt', 'vue', 'vue-router']

type Dependencies = Record<string, string> | undefined

// Что у сайта объявлено не так, как у движка: 'nuxt 4.5.2 → 4.6.2'. Сравнивается строка из package.json,
// '^4.6.2' — тоже расхождение: правило — точная версия. Не объявлено с одной из сторон — не проверить, пропуск
export function versionDiff(engine: Dependencies, site: Dependencies): string[] {
  if (!engine || !site) return []
  return GUARDED
    .filter(name => engine[name] && site[name] && site[name] !== engine[name])
    .map(name => `${name} ${site[name]} → ${engine[name]}`)
}

// dependencies из package.json; нет файла, битый JSON — undefined: подсказка не должна ронять сборку
export function readDependencies(file: string): Dependencies {
  try {
    return JSON.parse(readFileSync(file, 'utf8')).dependencies
  }
  catch {
    return undefined
  }
}
