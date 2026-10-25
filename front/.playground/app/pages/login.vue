<script setup lang="ts">
import type { AuthFormField, FormSubmitEvent } from '#ui/types'

useSeo({ title: 'Вход', isIndexed: false })
const auth = useAuth()
const route = useRoute()
const form = useTemplateRef('form')
const message = ref('')
const fieldList: AuthFormField[] = [
  { name: 'email', type: 'email', label: 'Email', placeholder: 'you@example.com', required: true },
  { name: 'password', type: 'password', label: 'Пароль', required: true },
]

async function onSubmit(event: FormSubmitEvent<{ email: string, password: string }>) {
  const { error } = await auth.login(event.data)
  message.value = error?.message ?? ''
  form.value?.formRef?.setErrors(toFormErrorList(error?.fieldMap))
  if (!error) await navigateTo(String(route.query.next || '/lk'))
}
</script>

<template>
  <UPageCard class="mx-auto max-w-md">
    <UAuthForm ref="form" title="Вход" icon="i-lucide-lock" :fields="fieldList" :submit="{ label: 'Войти' }" @submit="onSubmit">
      <template #validation>
        <UAlert v-if="message" color="error" icon="i-lucide-circle-alert" :title="message" />
      </template>
      <template #password-hint>
        <ULink to="/password-reset" class="text-primary">Забыли пароль?</ULink>
      </template>
      <template #footer>
        Нет аккаунта? <ULink to="/register" class="text-primary">Зарегистрироваться</ULink>
      </template>
    </UAuthForm>
  </UPageCard>
</template>
