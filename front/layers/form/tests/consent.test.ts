import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useSiteForm } from '../app/composables/useSiteForm'

const detail = { token: 'one-use', fill_seconds_min: 0, is_consent_required: true }
const post = vi.fn()
function setup() {
  vi.stubGlobal('ref', ref)
  vi.stubGlobal('onMounted', () => {})
  vi.stubGlobal('useApi', () => ({ GET: async () => ({ data: detail, error: null }), POST: post }))
  vi.stubGlobal('apiRequest', (value: unknown) => value)
  vi.stubGlobal('useRoute', () => ({ fullPath: '/callback' }))
  vi.stubGlobal('useMetrika', () => ({ reachGoal: vi.fn() }))
  vi.stubGlobal('fillWaitMs', () => 0)
  vi.stubGlobal('needsNewToken', () => false)
  vi.stubGlobal('localStorage', { getItem: () => null })
  vi.stubGlobal('document', { cookie: '' })
  vi.stubGlobal('readYmClientId', () => '')
  vi.stubGlobal('VISIT_KEY', 'test-visit')
}
beforeEach(() => { post.mockReset(); detail.is_consent_required = true; setup() })
afterEach(() => vi.unstubAllGlobals())

describe('согласие в фактическом теле заявки', () => {
  it('422 сохраняет поля/файлы/токен, успешная отправка снимает только согласие', async () => {
    const form = useSiteForm('callback')
    await form.load()
    form.fileIdList.value = ['uploaded-file']
    const fields = { name: 'Анна', phone: '+79990001122', consent: false }
    post.mockResolvedValueOnce({ data: null, error: { status: 422, message: 'Подтвердите согласие', fieldMap: { consent: 'Подтвердите согласие' } } })
    await form.submit(fields)
    expect(post.mock.calls[0][1].body).toMatchObject({ ...fields, token: 'one-use', file_id_list: ['uploaded-file'] })
    expect(form.error.value?.fieldMap.consent).toBe('Подтвердите согласие')
    expect(fields).toEqual({ name: 'Анна', phone: '+79990001122', consent: false })
    expect(form.fileIdList.value).toEqual(['uploaded-file'])
    fields.consent = true
    post.mockResolvedValue({ data: { message: 'Заявка отправлена' }, error: null })
    await form.submit(fields)
    expect(post.mock.calls[1][1].body.consent).toBe(true)
    expect(fields).toEqual({ name: 'Анна', phone: '+79990001122', consent: false })
    await form.submit(fields)
    expect(post.mock.calls[2][1].body.consent).toBe(false)
  })
  it('неподключённая галка сохраняет прежнее тело без consent', async () => {
    const form = useSiteForm('callback')
    await form.load()
    form.detail.value!.is_consent_required = false
    post.mockResolvedValue({ data: { message: 'OK' }, error: null })
    await form.submit({ phone: '+79990001122' })
    expect(post.mock.calls[0][1].body).not.toHaveProperty('consent')
  })
})
