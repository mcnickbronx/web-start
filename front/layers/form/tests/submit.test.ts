import { describe, expect, it } from 'vitest'
import { fillWaitMs, needsNewToken } from '../app/utils/submit'

describe('fillWaitMs', () => {
  it('ждём до 3 секунд с загрузки формы, дальше — сразу', () => {
    expect(fillWaitMs(1000, 2000, 3000)).toBe(2000)
    expect(fillWaitMs(1000, 5000, 3000)).toBe(0)
  })
})

describe('needsNewToken', () => {
  it('406 и ошибка капчи — новый токен, ошибки полей и сбои — нет', () => {
    expect(needsNewToken({ status: 406, fieldMap: {} })).toBe(true)
    expect(needsNewToken({ status: 422, fieldMap: { captcha: 'Капча не пройдена' } })).toBe(true)
    expect(needsNewToken({ status: 422, fieldMap: { phone: 'Укажите телефон или email', email: 'Укажите телефон или email' } })).toBe(false)
    for (const status of [0, 429, 500]) {
      expect(needsNewToken({ status, fieldMap: {} })).toBe(false)
    }
  })
})
