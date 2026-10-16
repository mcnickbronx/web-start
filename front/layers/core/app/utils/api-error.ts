/** Ошибка запроса в одном виде — что бы ни ответили: бэкенд, прокси или никто. */
export interface ApiError {
  /** Код ответа; 0 — ответа нет: пропала сеть или сервер недоступен */
  status: number
  /** Текст для пользователя */
  message: string
  /** Ошибки по полям (422): имя поля → текст — чтобы показать под полем */
  fieldMap: Record<string, string>
}

export type ApiResult<T> = { data: T, error: null } | { data: null, error: ApiError }

const STATUS_MESSAGE_MAP: Record<number, string> = {
  0: 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз',
  401: 'Нужно войти заново',
  403: 'Нет прав на это действие',
  404: 'Не найдено',
  429: 'Слишком много попыток. Подождите минуту и попробуйте снова',
}
const SERVER_ERROR_MESSAGE = 'Сервер не смог обработать запрос. Попробуйте ещё раз чуть позже'

/**
 * Ответ с ошибкой → ApiError.
 *
 * Бэкенд всегда отвечает {message}, у 422 ещё full_error: [{type, loc, msg}], где loc —
 * имя поля. Прокси отвечает без message (429 — лимит частоты Traefik, 502 — бэкенд лежит),
 * для таких кодов свой текст. Подробности 500 пользователю ни к чему — общий текст.
 */
export function parseApiError(status: number, body: unknown): ApiError {
  const data = (body && typeof body === 'object' ? body : {}) as { message?: unknown, full_error?: unknown }
  const fieldMap: Record<string, string> = {}
  if (Array.isArray(data.full_error)) {
    for (const item of data.full_error as { loc?: unknown, msg?: unknown }[]) {
      if (typeof item?.loc === 'string' && typeof item.msg === 'string' && !(item.loc in fieldMap)) {
        fieldMap[item.loc] = item.msg
      }
    }
  }
  let message = typeof data.message === 'string' ? data.message : ''
  if (status >= 500) {
    message = SERVER_ERROR_MESSAGE
  }
  return { status, message: message || STATUS_MESSAGE_MAP[status] || SERVER_ERROR_MESSAGE, fieldMap }
}

/**
 * Запрос клиента useApi() → { data } или { error } с текстом для пользователя, без исключений:
 *   const { data, error } = await apiRequest(api.GET('/api/page/list'))
 */
export async function apiRequest<T>(call: Promise<{ data?: T, error?: unknown, response: Response }>): Promise<ApiResult<T>> {
  try {
    const { data, error, response } = await call
    if (response.ok) {
      return { data: data as T, error: null }
    }
    return { data: null, error: parseApiError(response.status, error) }
  }
  catch {
    return { data: null, error: parseApiError(0, null) }
  }
}
