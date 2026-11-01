import type { components } from '#api-types'
import { useAuth } from './useAuth'

type Schema = components['schemas']

/** Загрузка серверного требования и отправка регистрации. Ошибка загрузки не означает False. */
export function useRegistration() {
  const auth = useAuth()
  const info = ref<Schema['RegistrationInfoOut'] | null>(null)
  const isLoading = ref(false)
  const loadError = ref<ApiError | null>(null)
  const consent = ref(false)
  const error = ref<ApiError | null>(null)

  async function load() {
    isLoading.value = true
    const result = await auth.registrationInfo()
    info.value = result.data
    loadError.value = result.error
    isLoading.value = false
    return result
  }

  async function submit(fields: Omit<Schema['RegisterIn'], 'consent'>) {
    if (!info.value || isLoading.value) return null
    const result = await auth.register({ ...fields, ...(consent.value ? { consent: true } : {}) })
    error.value = result.error
    if (!result.error) consent.value = false
    return result
  }

  onMounted(load)
  return { info, isLoading, loadError, consent, error, load, submit }
}
