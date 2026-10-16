<script lang="ts">
// Скрипт SmartCaptcha — один на страницу, сколько бы форм с капчей на ней ни было
interface SmartCaptchaApi {
  render: (container: HTMLElement, params: { sitekey: string, hl: string, callback: (token: string) => void }) => number
  subscribe: (widgetId: number, event: 'token-expired', callback: () => void) => void
  reset: (widgetId: number) => void
  destroy: (widgetId: number) => void
}

declare global {
  interface Window {
    smartCaptcha?: SmartCaptchaApi
    onSmartCaptchaLoad?: () => void
  }
}

let loading: Promise<SmartCaptchaApi> | undefined

function loadSmartCaptcha(): Promise<SmartCaptchaApi> {
  loading ??= new Promise((resolve, reject) => {
    if (window.smartCaptcha) {
      return resolve(window.smartCaptcha)
    }
    window.onSmartCaptchaLoad = () => resolve(window.smartCaptcha!)
    const script = document.createElement('script')
    script.src = 'https://smartcaptcha.yandexcloud.net/captcha.js?render=onload&onload=onSmartCaptchaLoad'
    script.defer = true
    script.onerror = () => {
      loading = undefined
      reject(new Error('SmartCaptcha не загрузилась'))
    }
    document.head.append(script)
  })
  return loading
}
</script>

<script setup lang="ts">
// Капча Яндекса (SmartCaptcha) — виджет «Я не робот», для форм с captcha_provider 'yandex':
//   <FormSmartCaptcha v-model="fields.captcha" :sitekey="detail.captcha_client_key" :form-token="detail.token" />
// Токен виджета одноразовый: новый токен формы (после отправки или ошибки капчи) сбрасывает виджет.
// sitekey — прямо из описания формы: пуст он там, только когда капча не Яндекса, а тогда виджета нет
const props = defineProps<{ sitekey?: string | null, formToken: string }>()
const token = defineModel<string>({ required: true })
const container = useTemplateRef('container')
const isFailed = ref(false)
let widgetId: number | undefined

onMounted(async () => {
  try {
    const smartCaptcha = await loadSmartCaptcha()
    if (!container.value) {
      return
    }
    widgetId = smartCaptcha.render(container.value, { sitekey: props.sitekey ?? '', hl: 'ru', callback: (value) => { token.value = value } })
    smartCaptcha.subscribe(widgetId, 'token-expired', () => { token.value = '' })
  }
  catch {
    isFailed.value = true
  }
})

watch(() => props.formToken, () => {
  if (widgetId !== undefined) {
    window.smartCaptcha?.reset(widgetId)
  }
  token.value = ''
})

onBeforeUnmount(() => {
  if (widgetId !== undefined) {
    window.smartCaptcha?.destroy(widgetId)
  }
})
</script>

<template>
  <div>
    <div ref="container" />
    <p v-if="isFailed" class="text-sm text-error">Не удалось загрузить капчу — обновите страницу</p>
  </div>
</template>
