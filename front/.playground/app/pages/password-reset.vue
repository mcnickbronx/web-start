<script setup lang="ts">
import type { AuthFormField, FormSubmitEvent } from '#ui/types'

// Забыли пароль: email → код из письма и новый пароль → сразу вход
const auth = useAuth()
const toast = useToast()
const form = useTemplateRef('form')
const step = ref<'email' | 'code'>('email')
const email = ref('')
const message = ref('')

const emailFieldList: AuthFormField[] = [{ name: 'email', type: 'email', label: 'Email', required: true }]
const codeFieldList: AuthFormField[] = [
  { name: 'code', type: 'otp', label: 'Код из письма', length: 6 },
  { name: 'password_new', type: 'password', label: 'Новый пароль', description: 'Не короче 8 символов', required: true },
  { name: 'password_new_confirm', type: 'password', label: 'Новый пароль ещё раз', required: true },
]

function showError(error: ApiError | null) {
  message.value = error?.message ?? ''
  form.value?.formRef?.setErrors(toFormErrorList(error?.fieldMap))
}

async function onEmail(event: FormSubmitEvent<{ email: string }>) {
  const { error } = await auth.requestPasswordReset(event.data.email)
  showError(error)
  if (!error) {
    email.value = event.data.email
    step.value = 'code'
  }
}

async function onCode(event: FormSubmitEvent<{ code: string[] | string, password_new: string, password_new_confirm: string }>) {
  const code = Array.isArray(event.data.code) ? event.data.code.join('') : event.data.code
  const { error } = await auth.confirmPasswordReset({ ...event.data, email: email.value, code })
  showError(error)
  if (!error) await navigateTo('/lk')
}

async function resend() {
  const { data, error } = await auth.requestPasswordReset(email.value)
  toast.add({ title: error?.message ?? data?.message ?? '', color: error ? 'error' : 'success' })
}
</script>

<template>
  <UPageCard class="mx-auto max-w-md">
    <UAuthForm v-if="step === 'email'" ref="form" title="Восстановление пароля" description="Пришлём код на почту" icon="i-lucide-key-round" :fields="emailFieldList" :submit="{ label: 'Выслать код' }" @submit="onEmail">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        Вспомнили? <ULink to="/login" class="text-primary">Войти</ULink>
      </template>
    </UAuthForm>
    <UAuthForm v-else ref="form" title="Новый пароль" :description="`Код отправлен на ${email}, если такой адрес зарегистрирован`" icon="i-lucide-mail-check" :fields="codeFieldList" :submit="{ label: 'Сменить пароль и войти' }" @submit="onCode">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #footer>
        <UButton label="Выслать код ещё раз" variant="link" @click="resend" />
      </template>
    </UAuthForm>
  </UPageCard>
</template>
