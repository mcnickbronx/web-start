import type { FormError } from '#ui/types'

/** Ошибки полей от бэкенда (fieldMap) — в setErrors формы Nuxt UI: текст встанет под своим полем */
export function toFormErrorList(fieldMap: Record<string, string> = {}): FormError[] {
  return Object.entries(fieldMap).map(([name, message]) => ({ name, message }))
}
