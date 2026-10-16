<script setup lang="ts">
// Лента статей: карточки и страницы-ссылки ?page=N — поисковик обходит их без скриптов
const props = defineProps<{
  result: PageFeedList
  /** Номер страницы ленты */
  page: number
  /** Статей на странице */
  row: number
}>()

const postList = computed(() => props.result.items.map(item => ({
  title: item.title,
  description: item.excerpt,
  date: item.date_published ? formatPageDate(item.date_published) : undefined,
  image: item.cover?.url,
  badge: item.category?.name,
  to: item.path,
})))
</script>

<template>
  <p v-if="!postList.length" class="text-muted">Здесь пока нет статей</p>
  <UBlogPosts v-else :posts="postList" />
  <UPagination
    v-if="result.total.count > row" class="mt-10 flex justify-center"
    :page="page" :total="result.total.count" :items-per-page="row" :to="(page: number) => ({ query: page > 1 ? { page } : {} })"
  />
</template>
