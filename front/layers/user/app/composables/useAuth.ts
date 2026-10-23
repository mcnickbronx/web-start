import type { components } from '#api-types'

type Schema = components['schemas']
export type UserMe = Schema['UserMeOut']

/**
 * Кабинет: вход, регистрация с кодом, пароли, профиль. Каждое действие возвращает
 * { data } или { error } с текстом для пользователя и ошибками по полям — см. core.
 *
 * Всё — прямо в API. После входа бэкенд отдаёт access, а refresh сам кладёт в httpOnly-куку:
 * скрипты страницы её не видят.
 */
export function useAuth() {
  const api = useApi()
  const access = useAccessToken()
  const user = useState<UserMe | null>('user:me', () => null)

  async function loadMe() {
    const result = await apiRequest(api.GET('/api/user/me'))
    user.value = result.data
    return result
  }

  /** Вход состоялся (вход, активация, пароли): access — в память, дальше — профиль */
  async function signIn(call: Promise<ApiResult<Schema['TokenOut']>>): Promise<ApiResult<UserMe | null>> {
    const result = await call
    if (result.error) {
      return result
    }
    access.value = result.data.access
    return loadMe()
  }

  /** Выход (этого устройства или всех): токены и профиль забываются, только если бэкенд ответил.
   * Не ответил — вход остаётся и в ответе ошибка: куку refresh стереть может только он */
  async function signOut<T>(call: Promise<ApiResult<T>>): Promise<ApiResult<T>> {
    const result = await call
    if (!result.error) {
      access.value = null
      user.value = null
    }
    return result
  }

  return {
    user,
    loadMe,

    login: (body: Schema['TokenPairIn']) => signIn(apiRequest(api.POST('/api/user/pair', { body }))),

    /** Регистрация без пароля: пользователь создаётся неактивным, код приходит на почту */
    register: (body: Schema['RegisterIn']) => apiRequest(api.POST('/api/user/register', { body })),
    /** Код из письма и пароль — активация и сразу вход. Пароль здесь: его задаёт только тот, у кого почта */
    activate: (body: Schema['ActivateIn']) => signIn(apiRequest(api.POST('/api/user/activate', { body }))),
    resendCode: (email: string) => apiRequest(api.POST('/api/user/activate/resend', { body: { email } })),

    /** Забыли пароль: код на почту. Ответ одинаковый, есть такой email или нет */
    requestPasswordReset: (email: string) => apiRequest(api.POST('/api/user/password/reset', { body: { email } })),
    confirmPasswordReset: (body: Schema['PasswordResetConfirmIn']) => signIn(apiRequest(api.POST('/api/user/password/reset/confirm', { body }))),
    /** Смена пароля: старые токены на всех устройствах перестают работать */
    changePassword: (body: Schema['PasswordChangeIn']) => signIn(apiRequest(api.POST('/api/user/password/change', { body }))),

    async updateProfile(body: Schema['UserUpdateIn']) {
      const result = await apiRequest(api.PATCH('/api/user/me', { body }))
      if (result.data) {
        user.value = result.data
      }
      return result
    },

    /** Выход на этом устройстве: бэкенд завершает его сессию, токены перестают работать сразу */
    logout: () => signOut(apiRequest(api.POST('/api/user/logout'))),
    /** Выход на всех устройствах, этом тоже */
    logoutAll: () => signOut(apiRequest(api.POST('/api/user/logout/all'))),

    /** Где пользователь вошёл: устройства, сначала недавние; это устройство — is_current */
    sessionList: () => apiRequest(api.GET('/api/user/session/list')),
    /** Выйти на другом устройстве: его токены перестают работать сразу */
    endSession: (id: string) => apiRequest(api.DELETE('/api/user/session/{session_id}', { params: { path: { session_id: id } } })),
  }
}
