/**
 * Ошибки полей без ошибки поля name — посетитель начал его исправлять. Вместе с ним гаснут поля
 * с тем же текстом: «Укажите телефон или email» стоит на обоих и исправляется любым из них.
 */
export function withoutFieldError(fieldMap: Record<string, string>, name: string): Record<string, string> {
  const message = fieldMap[name]
  return Object.fromEntries(Object.entries(fieldMap).filter(([, text]) => text !== message))
}
