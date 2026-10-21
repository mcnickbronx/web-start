/** Адрес страницы для canonical и og:url: сайт и путь, без параметров и якоря — с метками рекламы
 * (`?utm_source=…`, `yclid`) это та же страница. Склейка, а не `new URL(path, origin)`: путь `//evil.com/x`
 * или `/\evil.com` тот разобрал бы как чужой домен, а здесь хост — всегда хост сайта */
export function canonicalUrl(origin: string, path: string): string {
  const pathname = path.split(/[?#]/, 1)[0]!.replace(/^[/\\]+/, '')
  return `${new URL(origin).origin}/${pathname}`
}
