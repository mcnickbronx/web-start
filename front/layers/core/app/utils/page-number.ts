/** Номер страницы ленты из ?page=: мусор, ноль и отрицательные — первая страница */
export function parsePageNumber(value: unknown): number {
  const number = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(number) && number > 0 ? number : 1
}
