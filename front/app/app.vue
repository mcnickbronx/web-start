<script setup lang="ts">
import { ru } from '@nuxt/ui/locale'
</script>

<template>
  <UApp :locale="ru">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <CookieNotice />
  </UApp>
</template>
