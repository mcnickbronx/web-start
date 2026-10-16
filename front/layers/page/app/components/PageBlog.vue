<script setup lang="ts">
// Лента целиком — у /blog и у рубрик: заголовок, рубрики, карточки. Сайт перекрывает её
// или отдельные части: PageCategoryMenu, PageFeed
defineProps<{
  title: string
  description?: string
  result: PageFeedList
  /** Номер страницы ленты */
  page: number
  /** Статей на странице */
  row: number
}>()
</script>

<template>
  <UPageHeader :title="title" :description="description" class="mb-6" />
  <PageCategoryMenu />
  <PageFeed :result="result" :page="page" :row="row" />
</template>
