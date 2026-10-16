import { describe, expect, it } from 'vitest'
import { apiRequest, parseApiError } from '../app/utils/api-error'

describe('parseApiError', () => {
  it('422 — сообщение и ошибки по полям', () => {
    const error = parseApiError(422, {
      message: 'Обязательное поле; Слишком длинно',
      full_error: [{ type: 'missing', loc: 'phone', msg: 'Обязательное поле' }, { type: 'too_long', loc: 'name', msg: 'Слишком длинно' }],
    })
    expect(error).toEqual({ status: 422, message: 'Обязательное поле; Слишком длинно', fieldMap: { phone: 'Обязательное поле', name: 'Слишком длинно' } })
  })

  it('406 — текст бэкенда как есть', () => {
    expect(parseApiError(406, { message: 'Капча не пройдена, попробуйте ещё раз' }).message).toBe('Капча не пройдена, попробуйте ещё раз')
  })

  it('500 — общий текст вместо подробностей', () => {
    expect(parseApiError(500, { message: 'Внутренняя ошибка сервера' }).message).toMatch(/^Сервер не смог/)
  })

  it('ответ прокси без тела — свой текст по коду', () => {
    expect(parseApiError(429, 'Too Many Requests').message).toMatch(/Слишком много попыток/)
    expect(parseApiError(502, null).message).toMatch(/^Сервер не смог/)
  })

  it('нет ответа — про связь', () => {
    expect(parseApiError(0, null).message).toMatch(/^Нет связи/)
  })
})

describe('apiRequest', () => {
  const response = (status: number) => ({ ok: status < 400, status }) as Response

  it('успех — data без ошибки', async () => {
    expect(await apiRequest(Promise.resolve({ data: { id: 1 }, response: response(200) }))).toEqual({ data: { id: 1 }, error: null })
  })

  it('ошибка — error, data пусто', async () => {
    const result = await apiRequest(Promise.resolve({ error: { message: 'Нет' }, response: response(406) }))
    expect(result.data).toBeNull()
    expect(result.error?.message).toBe('Нет')
  })

  it('упала сеть — error со статусом 0, без исключения', async () => {
    const result = await apiRequest(Promise.reject(new TypeError('Failed to fetch')))
    expect(result.error?.status).toBe(0)
  })
})
