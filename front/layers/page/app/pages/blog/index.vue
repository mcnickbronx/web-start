<script setup lang="ts">
// Общая лента всех рубрик. Страница пересоздаётся на каждый адрес: ?page=2 — новый запрос при рендере
definePageMeta({ key: route => route.fullPath })

const route = useRoute()
const { blogTitle, blogDescription, feedRow } = useAppConfig().page
const pageNumber = parsePageNumber(route.query.page)
const feed = await usePageRequest(`page-list-${pageNumber}`, api => api.GET('/api/page/list', {
  params: { query: { page: pageNumber, row: feedRow } },
}))
// Пустая лента — 404, а не страница с кодом 200: ?page=9999 или статей нет вовсе. Лента есть на каждом
// сайте, и на сайте без блога пустой /blog иначе попал бы в поиск
if (!feed.items.length) {
  throw createError({ statusCode: 404, message: 'Страница не найдена', fatal: true })
}
useSeo({ title: blogTitle, description: blogDescription, page: pageNumber })
</script>

<template>
  <PageBlog :title="blogTitle" :description="blogDescription" :result="feed" :page="pageNumber" :row="feedRow" />
</template>
