/** Номер страницы ленты из ?page=: мусор, ноль и отрицательные — первая страница */
export function parsePageNumber(value: unknown): number {
  const number = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(number) && number > 0 ? number : 1
}

/** Адрес страницы ленты для canonical: кроме номера страницы — никаких параметров (с метками рекламы
 * это та же страница), у первой — и его нет */
export function feedPath(path: string, page: number): string {
  return page > 1 ? `${path}?page=${page}` : path
}
