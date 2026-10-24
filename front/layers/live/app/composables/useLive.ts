import type { Ref } from 'vue'

type LiveHandler = (event: LiveEvent) => void

interface Live {
  /** 'ready' — на связи; остальное — в live-connection.ts */
  status: Readonly<Ref<LiveStatus>>
  /** Подписка на события одного типа; вернёт отписку, в компоненте снимается сама */
  on: (type: string, handler: LiveHandler) => () => void
}

declare module '#app' {
  interface NuxtApp {
    /** Соединение вкладки — одно на все useLive() */
    _live?: Live
  }
}

/**
 * Живые события от модуля live бэкенда:
 *
 *   const live = useLive()
 *   live.on('order_paid', () => refresh())
 *
 * Соединение — одно на вкладку: открывается при первом useLive() с access-токеном, после выхода
 * закрывается, после нового входа открывается с новым токеном. Работает только в браузере.
 */
export function useLive(): Live {
  if (import.meta.server) {
    return { status: ref('idle'), on: () => () => {} }
  }
  const nuxtApp = useNuxtApp()
  nuxtApp._live ??= startLive(nuxtApp._refreshAccess)
  return nuxtApp._live
}

function startLive(refreshToken?: () => Promise<string | null>): Live {
  const access = useAccessToken()
  const status = ref<LiveStatus>('idle')
  const handlerMap = new Map<string, Set<LiveHandler>>()
  const connection = createLiveConnection({
    url: liveUrl(useRuntimeConfig().public.apiBase),
    getToken: () => access.value,
    refreshToken,
    onEvent: event => handlerMap.get(event.type)?.forEach(handler => handler(event)),
    onStatus: (value) => {
      status.value = value
    },
  })
  // Своя область, а не компонента, который первым позвал useLive(): уйдёт он со страницы — соединение останется
  effectScope(true).run(() => watch(access, () => connection.connect(), { immediate: true }))

  return {
    status: readonly(status),
    on(type, handler) {
      if (!handlerMap.has(type)) {
        handlerMap.set(type, new Set())
      }
      handlerMap.get(type)!.add(handler)
      const off = () => {
        handlerMap.get(type)?.delete(handler)
      }
      if (getCurrentScope()) {
        onScopeDispose(off)
      }
      return off
    },
  }
}
