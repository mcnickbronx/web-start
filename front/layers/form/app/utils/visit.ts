/** Откуда человек пришёл на сайт — то, что бэкенд ждёт в поле visit заявки. */
export interface Visit {
  referrer: string
  landing_page: string
  ym_client_id: string
}

export const VISIT_KEY = 'form:visit'
/** Сколько помнить источник, если человек потом заходит напрямую */
export const VISIT_TTL_MS = 30 * 24 * 60 * 60 * 1000

/** Параметры адреса, по которым источник считается рекламой или меткой, а не прямым заходом */
const MARKED_PARAM_RE = /(?:^|[?&])(?:utm_[a-z_]+|yclid|gclid)=/i

/**
 * Визит по текущей загрузке сайта: чужой referrer (свой сайт — не источник)
 * и первая страница вместе с параметрами — метки из неё разберёт бэкенд.
 */
export function buildVisit(referrer: string, pathWithQuery: string, siteHost: string): Omit<Visit, 'ym_client_id'> {
  let host = ''
  try {
    host = new URL(referrer).hostname.replace(/^www\./, '')
  }
  catch { /* пустой или кривой referrer — прямой заход */ }
  const isExternal = !!host && host !== siteHost.replace(/^www\./, '')
  return { referrer: isExternal ? referrer : '', landing_page: pathWithQuery }
}

/**
 * Перезаписать ли сохранённый визит новым. Правило как у Метрики — последний значимый
 * источник: новый заход с чужого сайта или с метками важнее, прямой заход — нет,
 * пока сохранённый не устарел.
 */
export function shouldReplaceVisit(stored: { date?: number } | null, next: Omit<Visit, 'ym_client_id'>, now: number): boolean {
  if (!stored?.date || now - stored.date > VISIT_TTL_MS) {
    return true
  }
  return !!next.referrer || MARKED_PARAM_RE.test(next.landing_page)
}

/** ClientID Яндекс Метрики из куки _ym_uid. Метрики нет — пусто. */
export function readYmClientId(cookieString: string): string {
  return /(?:^|;\s*)_ym_uid=(\d+)/.exec(cookieString)?.[1] ?? ''
}
