import { describe, expect, it } from 'vitest'
import { withoutFieldError } from '../app/utils/field-error'

describe('withoutFieldError', () => {
  it('гаснет исправляемое поле, остальные — нет', () => {
    expect(withoutFieldError({ name: 'Укажите имя', email: 'Некорректный email' }, 'name')).toEqual({ email: 'Некорректный email' })
  })

  it('общая ошибка нескольких полей гаснет на всех', () => {
    const fieldMap = { phone: 'Укажите телефон или email', email: 'Укажите телефон или email', name: 'Укажите имя' }
    expect(withoutFieldError(fieldMap, 'email')).toEqual({ name: 'Укажите имя' })
  })

  it('у поля нет ошибки — ничего не меняется', () => {
    expect(withoutFieldError({ name: 'Укажите имя' }, 'phone')).toEqual({ name: 'Укажите имя' })
  })
})
