import type { components } from '#api-types'

type Schema = components['schemas']
export type FormFields = Pick<Schema['FormRequestIn'], 'name' | 'phone' | 'email' | 'message' | 'data' | 'captcha'>

function readVisit(): Schema['VisitIn'] {
  let stored: Partial<Visit> = {}
  try {
    stored = JSON.parse(localStorage.getItem(VISIT_KEY) ?? '{}')
  }
  catch { /* нет localStorage — без источника */ }
  return { referrer: stored.referrer ?? '', landing_page: stored.landing_page ?? '', ym_client_id: readYmClientId(document.cookie) }
}

/**
 * Форма заявки по коду из админки (Заявки → Формы):
 *
 *   const { detail, error, trap, upload, submit, clearFieldError } = useSiteForm('callback')
 *   await upload(file)                   // если форма принимает файлы
 *   await submit({ phone, captcha })     // остальное — токен, файлы, ловушка, визит — само
 *   clearFieldError('phone')             // на ввод в поле: его ошибка гаснет
 *
 * Описание, токен и вопрос капчи загрузятся сами. В разметке формы обязательна ловушка
 * для ботов: <FormTrap v-model="trap" />.
 *
 * Форма грузится в браузере, когда компонент появился (onMounted), а не при серверном рендере:
 * иначе браузер получил бы её второй раз с другим токеном и вопросом капчи, а отсчёт ловушки
 * по времени пошёл бы от рендера на сервере.
 */
export function useSiteForm(code: string) {
  const api = useApi()
  const route = useRoute()
  const metrika = useMetrika()

  const detail = ref<Schema['FormDetailOut'] | null>(null)
  const error = ref<ApiError | null>(null)
  const isLoading = ref(false)
  const isSent = ref(false)
  const trap = ref('')
  const fileIdList = ref<string[]>([])
  let loadedAt = 0

  async function load() {
    const result = await apiRequest(api.GET('/api/form/detail/{code}', { params: { path: { code } } }))
    // Не загрузилась заново — остаётся прежняя: после отправки посетитель видит «Заявка отправлена»,
    // а не «Загрузка формы…» без конца. Отправить по ней ещё раз — 406, и форма запросится снова
    detail.value = result.data ?? detail.value
    error.value = result.error
    fileIdList.value = []
    loadedAt = Date.now()
    return result
  }

  onMounted(load)

  /** Посетитель начал исправлять поле — его ошибка (и такая же на соседних полях) гаснет до отправки */
  function clearFieldError(name: string) {
    if (error.value?.fieldMap[name]) {
      error.value = { ...error.value, fieldMap: withoutFieldError(error.value.fieldMap, name) }
    }
  }

  async function upload(file: File) {
    if (!detail.value) {
      return null
    }
    const result = await apiRequest(api.POST('/api/form/upload-file', {
      // В схеме API файл описан строкой (binary), а уходит File в FormData — отсюда приведения типов
      body: { token: detail.value.token, file: file as unknown as string },
      bodySerializer(body) {
        const formData = new FormData()
        formData.append('token', body.token)
        formData.append('file', body.file as unknown as Blob)
        return formData
      },
    }))
    if (result.data) {
      fileIdList.value.push(result.data.file_id)
    }
    error.value = result.error
    return result
  }

  async function submit(fields: FormFields) {
    if (!detail.value) {
      return null
    }
    isLoading.value = true
    const waitMs = fillWaitMs(loadedAt, Date.now(), detail.value.fill_seconds_min * 1000)
    await new Promise(resolve => setTimeout(resolve, waitMs))
    const result = await apiRequest(api.POST('/api/form/create', {
      body: {
        ...fields,
        token: detail.value.token,
        file_id_list: fileIdList.value,
        leave_empty: trap.value,
        source: route.fullPath,
        visit: readVisit(),
      },
    }))
    isLoading.value = false
    error.value = result.error
    isSent.value = !result.error
    // Цель в Метрике для каждой формы своя: form_callback и т. п. Счётчика нет — вызов пустой
    if (isSent.value) {
      metrika.reachGoal(`form_${code}`)
    }
    // После отправки токен израсходован; после ошибки токена или капчи — нужен новый.
    // load() сбрасывает ошибку — возвращаем ошибку отправки, чтобы посетитель её увидел
    if (!result.error || needsNewToken(result.error)) {
      await load()
      error.value = result.error
    }
    return result
  }

  return { detail, error, isLoading, isSent, trap, fileIdList, load, upload, submit, clearFieldError }
}
