declare global {
  interface Window {
    ym?: (counterId: number, method: string, ...args: unknown[]) => void
  }
}

/**
 * Яндекс Метрика: цели и параметры визита. Счётчик включается номером в NUXT_PUBLIC_METRIKA_ID;
 * без него и на сервере вызовы ничего не делают — звать можно откуда угодно.
 *
 *   useMetrika().reachGoal('form_callback')
 */
export function useMetrika() {
  const counterId = Number(useRuntimeConfig().public.metrikaId) || 0

  function reachGoal(goal: string, params?: Record<string, unknown>) {
    if (counterId && import.meta.client && readCookieChoice() !== 'declined') {
      window.ym?.(counterId, 'reachGoal', goal, params)
    }
  }

  return { counterId, reachGoal }
}
