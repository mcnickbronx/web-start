/** Адрес страницы для canonical и og:url: сайт и путь, без параметров и якоря — с метками рекламы
 * (`?utm_source=…`, `yclid`) это та же страница. Склейка, а не `new URL(path, origin)`: путь `//evil.example/x`
 * или `/\evil.example` тот разобрал бы как чужой домен, а здесь хост — всегда хост сайта.
 * У ленты со второй страницы — `?page=N`: это другая страница, а метки рекламы — нет */
export function canonicalUrl(origin: string, path: string, page = 1): string {
  const pathname = path.split(/[?#]/, 1)[0]!.replace(/^[/\\]+/, '')
  const query = Number.isInteger(page) && page > 1 ? `?page=${page}` : ''
  return `${new URL(origin).origin}/${pathname}${query}`
}
