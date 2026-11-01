import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useRegistration } from '../app/composables/useRegistration'

const get = vi.fn()
const post = vi.fn()
beforeEach(() => {
  get.mockReset(); post.mockReset()
  vi.stubGlobal('ref', ref)
  vi.stubGlobal('onMounted', () => {})
  vi.stubGlobal('useApi', () => ({ GET: get, POST: post }))
  vi.stubGlobal('useAccessToken', () => ref(null))
  vi.stubGlobal('useState', (_key: string, initial: () => unknown) => ref(initial()))
  vi.stubGlobal('apiRequest', (value: unknown) => value)
})
afterEach(() => vi.unstubAllGlobals())

describe('серверные условия и тело регистрации', () => {
  it('загрузка/сбой не превращаются в успешное False; повтор получает серверное требование', async () => {
    let resolve: (value: unknown) => void = () => {}
    get.mockReturnValueOnce(new Promise(done => { resolve = done }))
    const registration = useRegistration()
    expect(registration.consent.value).toBe(false)
    const loading = registration.load()
    expect(registration.isLoading.value).toBe(true)
    expect(await registration.submit({ email: 'reader@example.com' })).toBeNull()
    resolve({ data: null, error: { status: 0, message: 'Нет связи', fieldMap: {} } })
    await loading
    expect(registration.info.value).toBeNull()
    expect(registration.loadError.value?.message).toBe('Нет связи')
    expect(await registration.submit({ email: 'reader@example.com' })).toBeNull()
    expect(post).not.toHaveBeenCalled()
    get.mockResolvedValue({ data: { is_consent_required: true }, error: null })
    await registration.load()
    expect(get).toHaveBeenCalledWith('/api/user/registration/info')
    expect(registration.info.value?.is_consent_required).toBe(true)
    expect(registration.loadError.value).toBeNull()
  })
  it('отправляет только действие человека; 422 сохраняет поля, успех снимает согласие', async () => {
    get.mockResolvedValue({ data: { is_consent_required: true }, error: null })
    const registration = useRegistration()
    await registration.load()
    const fields = { email: 'reader@example.com', first_name: 'Читатель' }
    post.mockResolvedValueOnce({ data: null, error: { status: 422, message: 'Подтвердите согласие', fieldMap: { consent: 'Подтвердите согласие' } } })
    await registration.submit(fields)
    expect(post.mock.calls[0]).toEqual(['/api/user/register', { body: fields }])
    expect(registration.error.value?.fieldMap.consent).toBe('Подтвердите согласие')
    expect(fields).toEqual({ email: 'reader@example.com', first_name: 'Читатель' })
    registration.consent.value = true
    post.mockResolvedValue({ data: { message: 'Код отправлен' }, error: null })
    await registration.submit(fields)
    expect(post.mock.calls[1][1].body).toEqual({ ...fields, consent: true })
    expect(registration.consent.value).toBe(false)
    await registration.submit(fields)
    expect(post.mock.calls[2][1].body).not.toHaveProperty('consent')
  })
  it('False от сервера допускает прежнее тело без нового поля', async () => {
    get.mockResolvedValue({ data: { is_consent_required: false }, error: null })
    post.mockResolvedValue({ data: { message: 'Код отправлен' }, error: null })
    const registration = useRegistration()
    await registration.load()
    await registration.submit({ email: 'reader@example.com' })
    expect(post.mock.calls[0][1].body).toEqual({ email: 'reader@example.com' })
  })
})
