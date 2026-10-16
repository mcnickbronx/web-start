<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const auth = useAuth()
const toast = useToast()
const itemList: NavigationMenuItem[] = [
  { label: 'Статьи', icon: 'i-lucide-newspaper', to: '/lk', exact: true },
  { label: 'Профиль', icon: 'i-lucide-user', to: '/lk/profile' },
  { label: 'На сайт', icon: 'i-lucide-globe', to: '/' },
]

async function logout() {
  const { error } = await auth.logout()
  if (error) {
    toast.add({ title: error.message, color: 'error' })
    return
  }
  await navigateTo('/login')
}
</script>

<template>
  <UDashboardGroup>
    <UDashboardSidebar collapsible resizable>
      <template #header="{ collapsed }">
        <span v-if="!collapsed" class="font-semibold">Демо-сайт</span>
      </template>
      <template #default="{ collapsed }">
        <UNavigationMenu :items="itemList" :collapsed="collapsed" orientation="vertical" />
      </template>
      <template #footer="{ collapsed }">
        <UUser v-if="!collapsed" :name="auth.user.value?.email" size="sm" class="flex-1 truncate" />
        <UButton icon="i-lucide-log-out" color="neutral" variant="ghost" aria-label="Выйти" @click="logout" />
      </template>
    </UDashboardSidebar>
    <slot />
  </UDashboardGroup>
</template>
