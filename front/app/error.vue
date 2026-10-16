<script setup lang="ts">
import type { NuxtError } from '#app'
import { ru } from '@nuxt/ui/locale'

// Страница ошибки: 404 и сбои. Рисуется вместо app.vue, поэтому своя обёртка UApp с локалью.
// Посетитель видит у 404 всегда текст отсюда, у сбоя — message ошибки; message из createError у 404
// остаётся в журнале сервера. Текст в createError — в message: statusMessage уходит в строку статуса
// HTTP, где только латиница. Ниже statusMessage — заголовок для UError, в HTTP он не попадает
const props = defineProps<{ error: NuxtError }>()
const error = computed(() => props.error.statusCode === 404
  ? { statusCode: 404, statusMessage: 'Страница не найдена', message: 'Возможно, её удалили или адрес набран с ошибкой' }
  : { statusCode: props.error.statusCode, statusMessage: 'Не удалось открыть страницу', message: props.error.message })
useHead({ title: () => error.value.statusMessage })
</script>

<template>
  <UApp :locale="ru">
    <UError :error="error" :clear="{ label: 'На главную' }" />
  </UApp>
</template>
