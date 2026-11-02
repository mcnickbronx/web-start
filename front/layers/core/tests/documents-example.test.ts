import { readFileSync, existsSync } from 'node:fs'
import { afterEach, expect, it, vi } from 'vitest'
import { nextTick, onMounted, reactive, ref, useTemplateRef } from 'vue'
import { useSiteForm } from '../../form/app/composables/useSiteForm'
import { useRegistration } from '../../user/app/composables/useRegistration'
import { saveCookieChoice } from '../app/utils/cookie-choice'
import { mount } from './component-renderer'
import ts from 'typescript'

const demo = new URL('../../../.playground/app/', import.meta.url)
const config = (() => {
  const source = readFileSync(new URL('app.config.ts', demo), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const result: { default?: any } = {}
  new Function('defineAppConfig', 'exports', code)((value: unknown) => value, result)
  return result.default
})()
let views: ReturnType<typeof mount>[] = []
afterEach(() => { views.forEach(view => view.unmount()); views = []; vi.unstubAllGlobals() })

it('две настройки демо указывают на реальные разные страницы в sitemap', () => {
  expect(config.cookieNotice.policyUrl).not.toBe(config.personalData.consentUrl)
  for (const url of [config.cookieNotice.policyUrl, config.personalData.consentUrl]) {
    expect(url).toMatch(/^\/[a-z-]+$/)
    expect(existsSync(new URL(`pages${url}.vue`, demo))).toBe(true)
    expect(config.page.sitemapPageList).toContain(url)
    expect(readFileSync(new URL('layouts/default.vue', demo), 'utf8')).toContain(`to="${url}"`)
  }
})

it.each([false, true])('API is_consent_required=%s: настоящее демо независимо от ответа cookie', async required => {
  const post = vi.fn(async (_path: string, options: { body: Record<string, unknown> }) => required && options.body.consent !== true
    ? { data: null, error: { status: 422, fieldMap: { consent: 'Отдельный выбор' } } }
    : { data: { message: 'OK' }, error: null })
  const detail = { is_consent_required: required, required_field_list: [], token: 'synthetic', fill_seconds_min: 0 }
  const get = vi.fn(async () => ({ data: detail, error: null }))
  const storage = new Map<string, string>()
  let form: ReturnType<typeof useSiteForm>
  let registration: ReturnType<typeof useRegistration>
  const globals = {
    ref, reactive, onMounted, useTemplateRef,
    useAppConfig: () => config,
    useSiteForm: (code: string) => (form = useSiteForm(code)),
    useRegistration: () => (registration = useRegistration()),
    useApi: () => ({ GET: get, POST: post }), apiRequest: (value: unknown) => value,
    useAccessToken: () => ref(null), useState: (_key: string, initial: () => unknown) => ref(initial()),
    useAuth: () => ({}), useSeo: () => {}, useToast: () => ({}),
    useRoute: () => ({ fullPath: '/' }), useMetrika: () => ({ reachGoal: vi.fn() }),
    fillWaitMs: () => 0, needsNewToken: () => false, readYmClientId: () => '', VISIT_KEY: 'form:visit',
    localStorage: { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) },
    document: { cookie: '' },
  }
  for (const [key, value] of Object.entries(globals)) vi.stubGlobal(key, value)
  for (const choice of ['accepted', 'declined'] as const) {
    saveCookieChoice(choice)
    const formView = mount(new URL('pages/index.vue', demo))
    const registrationView = mount(new URL('pages/register.vue', demo))
    views.push(formView, registrationView)
    await Promise.resolve(); await Promise.resolve(); await nextTick()
    for (const view of [formView, registrationView]) {
      expect(view.find('UCheckbox')).toHaveLength(required ? 1 : 0)
      if (required) {
        expect(view.find('UCheckbox')[0].props.modelValue).toBe(false)
        expect(view.find('ULink').some(node => node.props.to === config.personalData.consentUrl)).toBe(true)
      }
    }
    expect(registration!.consent.value).toBe(false)
    const formResult = await form!.submit({ phone: 'synthetic', consent: false })
    expect(formResult?.error?.fieldMap.consent ?? null).toBe(required ? 'Отдельный выбор' : null)
    expect(post.mock.calls.at(-1)![1].body.consent).toBe(false)
    const registrationResult = await registration!.submit({ email: 'reader@example.com' })
    expect(registrationResult?.error?.fieldMap.consent ?? null).toBe(required ? 'Отдельный выбор' : null)
    expect(post.mock.calls.at(-1)![1].body).not.toHaveProperty('consent')
    if (required) {
      registration!.consent.value = true
      await registration!.submit({ email: 'reader@example.com' })
      expect(post.mock.calls.at(-1)![1].body.consent).toBe(true)
    }
    formView.unmount(); registrationView.unmount()
  }
})
