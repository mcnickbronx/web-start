<script setup lang="ts">
import type { components } from '#api-types'

// Статья или отдельная страница. HTML собран и очищен бэкендом (скрипты, фреймы, стили вырезаны)
defineProps<{ page: components['schemas']['PageDetailOut'] }>()
</script>

<template>
  <article class="mx-auto max-w-3xl">
    <UPageHeader :title="page.title" :headline="page.category?.name">
      <template v-if="page.category && page.date_published" #description>
        {{ formatPageDate(page.date_published) }}
      </template>
    </UPageHeader>
    <img v-if="page.cover" :src="page.cover.url" :alt="page.cover.alt || page.title" class="mt-8 w-full rounded-lg">
    <div class="prose mt-8 max-w-none dark:prose-invert" v-html="page.content_html" />
  </article>
</template>
