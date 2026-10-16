<script setup lang="ts">
import type { AuthFormField, FormSubmitEvent } from '@nuxt/ui'

const auth = useAuth()
const toast = useToast()
const form = useTemplateRef('form')
const step = ref<'form' | 'code'>('form')
const email = ref('')
const message = ref('')

const registerFieldList: AuthFormField[] = [
  { name: 'email', type: 'email', label: 'Email', required: true },
  { name: 'first_name', type: 'text', label: 'Имя' },
  { name: 'last_name', type: 'text', label: 'Фамилия' },
  { name: 'password', type: 'password', label: 'Пароль', description: 'Не короче 8 символов', required: true },
  { name: 'password_confirm', type: 'password', label: 'Пароль ещё раз', required: true },
]
const codeFieldList: AuthFormField[] = [{ name: 'code', type: 'otp', label: 'Код из письма', length: 6 }]

function showError(error: ApiError | null) {
  message.value = error?.message ?? ''
  form.value?.formRef?.setErrors(toFormErrorList(error?.fieldMap))
}

async function onRegister(event: FormSubmitEvent<{ email: string, password: string, password_confirm: string, first_name?: string, last_name?: string }>) {
  const { error } = await auth.register(event.data)
  showError(error)
  if (!error) {
    email.value = event.data.email
    step.value = 'code'
  }
}

async function onCode(event: FormSubmitEvent<{ code: string[] | string }>) {
  const code = Array.isArray(event.data.code) ? event.data.code.join('') : event.data.code
  const { error } = await auth.activate({ email: email.value, code })
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
    <UAuthForm v-if="step === 'form'" ref="form" title="Регистрация" icon="i-lucide-user-plus" :fields="registerFieldList" :submit="{ label: 'Зарегистрироваться' }" @submit="onRegister">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        Уже есть аккаунт? <ULink to="/login" class="text-primary">Войти</ULink>
      </template>
    </UAuthForm>
    <UAuthForm v-else ref="form" title="Подтверждение email" :description="`Код отправлен на ${email}`" icon="i-lucide-mail-check" :fields="codeFieldList" :submit="{ label: 'Подтвердить' }" @submit="onCode">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        <UButton label="Выслать код ещё раз" variant="link" @click="resend" />
      </template>
    </UAuthForm>
  </UPageCard>
</template>
