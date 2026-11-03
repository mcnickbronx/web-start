import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const access = ref<string | null>(null)
const refresh = vi.fn()
const navigate = vi.fn()

beforeEach(() => {
  access.value = null
  refresh.mockReset()
  navigate.mockReset()
  vi.stubGlobal('defineNuxtRouteMiddleware', (handler: unknown) => handler)
  vi.stubGlobal('useAccessToken', () => access)
  vi.stubGlobal('useNuxtApp', () => ({ _refreshAccess: refresh }))
  vi.stubGlobal('navigateTo', navigate)
})
afterEach(() => vi.unstubAllGlobals())

describe('доступ в кабинет', () => {
  it('гость после неудачного восстановления попадает на вход с адресом возврата', async () => {
    const { default: auth } = await import('../app/middleware/auth')
    await auth({ fullPath: '/lk/profile?tab=sessions' } as never, {} as never)
    expect(refresh).toHaveBeenCalledOnce()
    expect(navigate).toHaveBeenCalledWith({ path: '/login', query: { next: '/lk/profile?tab=sessions' } })
  })

  it('восстановленный вход допускает посетителя', async () => {
    refresh.mockImplementation(async () => { access.value = 'synthetic-access' })
    const { default: auth } = await import('../app/middleware/auth')
    await auth({ fullPath: '/lk' } as never, {} as never)
    expect(refresh).toHaveBeenCalledOnce()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('с действующим входом не обновляет токен и не перенаправляет', async () => {
    access.value = 'synthetic-access'
    const { default: auth } = await import('../app/middleware/auth')
    await auth({ fullPath: '/lk' } as never, {} as never)
    expect(refresh).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })
})
