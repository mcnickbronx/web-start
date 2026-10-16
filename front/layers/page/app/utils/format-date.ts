// Часовой пояс сайта. Явно, а не пояс машины: сервер в контейнере живёт в UTC, браузер посетителя —
// в своём поясе, и дата после полуночи разошлась бы между серверным HTML и браузером
const SITE_TIME_ZONE = 'Europe/Moscow'

/** Дата публикации для людей: «29 сентября 2026 г.» */
export function formatPageDate(value: string): string {
  return new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: SITE_TIME_ZONE })
}
