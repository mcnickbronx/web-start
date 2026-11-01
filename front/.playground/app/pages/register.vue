<script setup lang="ts">
import type { AuthFormField, FormSubmitEvent } from '#ui/types'

useSeo({ title: 'Регистрация', isIndexed: false })
const auth = useAuth()
const registration = useRegistration()
const { personalData } = useAppConfig()
const toast = useToast()
const form = useTemplateRef('form')
const step = ref<'form' | 'code'>('form')
const email = ref('')
const message = ref('')

// Пароль — на шаге кода, а не регистрации: его задаёт только тот, у кого почта
const registerFieldList: AuthFormField[] = [
  { name: 'email', type: 'email', label: 'Email', required: true },
  { name: 'first_name', type: 'text', label: 'Имя' },
  { name: 'last_name', type: 'text', label: 'Фамилия' },
]
const codeFieldList: AuthFormField[] = [
  { name: 'code', type: 'otp', label: 'Код из письма', length: 6 },
  { name: 'password', type: 'password', label: 'Пароль', description: 'Не короче 8 символов', required: true },
  { name: 'password_confirm', type: 'password', label: 'Пароль ещё раз', required: true },
]

function showError(error: ApiError | null) {
  message.value = error?.message ?? ''
  form.value?.formRef?.setErrors(toFormErrorList(error?.fieldMap))
}

async function onRegister(event: FormSubmitEvent<{ email: string, first_name?: string, last_name?: string }>) {
  const result = await registration.submit(event.data)
  if (!result) return
  const { error } = result
  showError(error)
  if (!error) {
    email.value = event.data.email
    step.value = 'code'
  }
}

async function onCode(event: FormSubmitEvent<{ code: string[] | string, password: string, password_confirm: string }>) {
  const code = Array.isArray(event.data.code) ? event.data.code.join('') : event.data.code
  const { error } = await auth.activate({ ...event.data, email: email.value, code })
  showError(error)
  if (!error) await navigateTo('/lk')
}

async function resend() {
  const { data, error } = await auth.resendCode(email.value)
  toast.add({ title: error?.message ?? data?.message ?? '', color: error ? 'error' : 'success' })
}
</script>

<template>
  <UPageCard class="mx-auto max-w-md">
    <p v-if="step === 'form' && registration.isLoading.value" class="text-muted">Загрузка условий регистрации…</p>
    <UAlert v-if="step === 'form' && registration.loadError.value" color="error" :title="registration.loadError.value.message">
      <template #actions><UButton label="Повторить загрузку" @click="registration.load" /></template>
    </UAlert>
    <UAuthForm v-if="step === 'form' && registration.info.value" ref="form" title="Регистрация" icon="i-lucide-user-plus" :fields="registerFieldList" :submit="{ label: 'Получить код' }" @submit="onRegister">
      <template #validation>
        <UFormField v-if="registration.info.value?.is_consent_required" name="consent" :error="registration.error.value?.fieldMap.consent" required>
          <UCheckbox v-model="registration.consent.value" label="Согласие на обработку персональных данных" />
          <ULink v-if="personalData.consentUrl" :to="personalData.consentUrl" target="_blank" class="text-primary">Текст согласия</ULink>
        </UFormField>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        Уже есть аккаунт? <ULink to="/login" class="text-primary">Войти</ULink>
      </template>
    </UAuthForm>
    <UAuthForm v-if="step === 'code'" ref="form" title="Подтверждение email" :description="`Код отправлен на ${email}`" icon="i-lucide-mail-check" :fields="codeFieldList" :submit="{ label: 'Подтвердить' }" @submit="onCode">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        <UButton label="Выслать код ещё раз" variant="link" @click="resend" />
      </template>
    </UAuthForm>
  </UPageCard>
</template>
