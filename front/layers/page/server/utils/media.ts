/** Адрес картинки на бэкенде для пути вида /media/page/2026/09/a.webp — или null, если путь уводит
 * из /media/ (/media/%2e%2e/api/… — иначе сайт стал бы прокси ко всему бэкенду: API и админке) */
export function mediaUrl(path: string, apiBase: string): string | null {
  const url = new URL(path, apiBase)
  return url.pathname.startsWith('/media/') ? url.href : null
}
