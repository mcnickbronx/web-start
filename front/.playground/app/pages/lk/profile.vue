<script setup lang="ts">
definePageMeta({ layout: 'lk', middleware: 'auth' })

const auth = useAuth()
const toast = useToast()
await auth.loadMe()

const profileForm = useTemplateRef('profileForm')
const passwordForm = useTemplateRef('passwordForm')
const profile = reactive({ first_name: auth.user.value?.first_name ?? '', last_name: auth.user.value?.last_name ?? '' })
const password = reactive({ password_current: '', password_new: '', password_new_confirm: '' })
const { data: sessionList, refresh: refreshSessionList } = await useAsyncData('user-session-list', async () => (await auth.sessionList()).data ?? [])

async function onProfile() {
  const { error } = await auth.updateProfile(profile)
  profileForm.value?.setErrors(toFormErrorList(error?.fieldMap))
  toast.add({ title: error?.message ?? 'Сохранено', color: error ? 'error' : 'success' })
}

async function onPassword() {
  const { error } = await auth.changePassword(password)
  passwordForm.value?.setErrors(toFormErrorList(error?.fieldMap))
  toast.add({ title: error?.message ?? 'Пароль изменён', color: error ? 'error' : 'success' })
  if (!error) Object.assign(password, { password_current: '', password_new: '', password_new_confirm: '' })
  await refreshSessionList()
}

async function onEndSession(id: string) {
  const { error } = await auth.endSession(id)
  toast.add({ title: error?.message ?? 'На том устройстве — выход', color: error ? 'error' : 'success' })
  await refreshSessionList()
}

async function onLogoutAll() {
  const { error } = await auth.logoutAll()
  if (error) {
    toast.add({ title: error.message, color: 'error' })
    return
  }
  await navigateTo('/login')
}
</script>

<template>
  <UDashboardPanel>
    <template #header>
      <UDashboardNavbar title="Профиль" />
    </template>
    <template #body>
      <div class="max-w-xl space-y-6">
        <UPageCard title="Личные данные" :description="auth.user.value?.email">
          <UForm ref="profileForm" :state="profile" class="space-y-4" @submit="onProfile">
            <UFormField name="first_name" label="Имя">
              <UInput v-model="profile.first_name" class="w-full" />
            </UFormField>
            <UFormField name="last_name" label="Фамилия">
              <UInput v-model="profile.last_name" class="w-full" />
            </UFormField>
            <UButton type="submit" label="Сохранить" loading-auto />
          </UForm>
        </UPageCard>
        <UPageCard title="Смена пароля" description="После смены на других устройствах придётся войти заново">
          <UForm ref="passwordForm" :state="password" class="space-y-4" @submit="onPassword">
            <UFormField name="password_current" label="Текущий пароль" required>
              <UInput v-model="password.password_current" type="password" autocomplete="current-password" class="w-full" />
            </UFormField>
            <UFormField name="password_new" label="Новый пароль" description="Не короче 8 символов" required>
              <UInput v-model="password.password_new" type="password" autocomplete="new-password" class="w-full" />
            </UFormField>
            <UFormField name="password_new_confirm" label="Новый пароль ещё раз" required>
              <UInput v-model="password.password_new_confirm" type="password" autocomplete="new-password" class="w-full" />
            </UFormField>
            <UButton type="submit" label="Сменить пароль" loading-auto />
          </UForm>
        </UPageCard>
        <UPageCard title="Где я вошёл" description="Выйти на устройстве — его вход перестанет работать сразу">
          <ul class="divide-y divide-default">
            <li v-for="session in sessionList" :key="session.id" class="flex items-center justify-between gap-4 py-2">
              <div>
                <p>{{ session.device || 'Неизвестное устройство' }}<span v-if="session.is_current" class="text-muted"> — это устройство</span></p>
                <p class="text-sm text-muted">{{ session.ip }}, активность {{ new Date(session.date_used).toLocaleString('ru-RU') }}</p>
              </div>
              <UButton v-if="!session.is_current" label="Выйти" color="neutral" variant="outline" size="sm" @click="onEndSession(session.id)" />
            </li>
          </ul>
          <UButton label="Выйти на всех устройствах" color="error" variant="soft" @click="onLogoutAll" />
        </UPageCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
