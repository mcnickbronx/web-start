import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, onMounted, ref } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { COOKIE_CHOICE_KEY, readCookieChoice, saveCookieChoice } from '../app/utils/cookie-choice'
import { mount } from './component-renderer'

const path = new URL('../app/components/CookieNotice.vue', import.meta.url)
let storage: Map<string, string>
let mounted: ReturnType<typeof mount>[]
function notice(isEnabled = true, router?: Router) {
  vi.stubGlobal('useAppConfig', () => ({ cookieNotice: { isEnabled, policyUrl: '/privacy' } }))
  const result = mount(path, router)
  mounted.push(result)
  return result
}
beforeEach(() => {
  storage = new Map()
  mounted = []
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) })
  for (const [key, value] of Object.entries({ ref, onMounted, readCookieChoice, saveCookieChoice })) vi.stubGlobal(key, value)
})
afterEach(() => { mounted.forEach(value => value.unmount()); vi.unstubAllGlobals() })

describe('ответ cookie в прежнем хранилище', () => {
  it.each([null, '', 'rejected', 'true', '<script>alert(1)</script>', 'x'.repeat(100_000)])('пустое или плохое значение (%#. ввод) — ответа нет', value => {
    if (value !== null) storage.set(COOKIE_CHOICE_KEY, value)
    expect(readCookieChoice()).toBeNull()
  })
  it.each(['accepted', 'declined'] as const)('сохраняет и читает %s', choice => {
    saveCookieChoice(choice)
    expect([...storage]).toEqual([['cookie-choice', choice]])
    expect(readCookieChoice()).toBe(choice)
  })
  it('ошибки чтения и записи не выходят наружу', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('quota') } })
    expect(readCookieChoice()).toBeNull()
    expect(() => saveCookieChoice('declined')).not.toThrow()
  })
})

describe('настоящий CookieNotice: mount и действия', () => {
  it.each([null, 'мусор'])('новый/неверный ответ показывает окно и реальную ссылку', async value => {
    if (value) storage.set(COOKIE_CHOICE_KEY, value)
    const view = notice()
    await nextTick()
    expect(view.find('div').some(node => node.props.role === 'region')).toBe(true)
    expect(view.find('ULink')[0].props.to).toBe('/privacy')
    expect(view.find('UButton').map(node => node.props.label)).toEqual(['Принять', 'Отклонить'])
  })
  it.each([['Принять', 'accepted'], ['Отклонить', 'declined']] as const)('%s скрывает окно, переход и новая загрузка помнят ответ', async (label, choice) => {
    const router = createRouter({ history: createMemoryHistory(), routes: ['/', '/privacy'].map(path => ({ path, component: { render: () => null } })) })
    await router.push('/')
    const view = notice(true, router)
    await nextTick()
    view.find('UButton').find(node => node.props.label === label)!.props.onClick()
    await router.push('/privacy')
    await nextTick()
    expect(router.currentRoute.value.path).toBe('/privacy')
    expect(view.find('UButton')).toHaveLength(0)
    expect(readCookieChoice()).toBe(choice)
    view.unmount()
    const reload = notice()
    await nextTick()
    expect(reload.find('UButton')).toHaveLength(0)
  })
  it('isEnabled=false не показывает окно', async () => {
    const view = notice(false)
    await nextTick()
    expect(view.find('UButton')).toHaveLength(0)
  })
  it('запрет storage не мешает закрыть окно; следующий визит спрашивает снова', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') } })
    const view = notice()
    await nextTick()
    expect(view.find('UButton')).toHaveLength(2)
    view.find('UButton')[0].props.onClick()
    await nextTick()
    expect(view.find('UButton')).toHaveLength(0)
    view.unmount()
    const reload = notice()
    await nextTick()
    expect(reload.find('UButton')).toHaveLength(2)
  })
})
