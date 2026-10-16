<script setup lang="ts">
// Адрес в корне сайта — рубрика или отдельная страница из админки: что именно, отвечает бэкенд
// одним запросом. Статьи здесь не ищутся — они живут по адресу /рубрика/статья. Страницы
// фронта (/login, /blog) сюда не попадают — у них свои маршруты.
// Страница пересоздаётся на каждый адрес: другой слаг или ?page=2 — новый запрос при рендере
definePageMeta({ key: route => route.fullPath })

const route = useRoute()
const slug = String(route.params.slug)
const pageNumber = parsePageNumber(route.query.page)
const { feedRow } = useAppConfig().page
const { category, page } = await usePageRequest(`page-resolve-${slug}`, api => api.GET('/api/page/resolve/{slug}', {
  params: { path: { slug } },
}))
if (!category && !page) {
  throw createError({ statusCode: 404, message: 'Страница не найдена', fatal: true })
}

// У рубрики — лента её статей
const feed = category
  ? await usePageRequest(`page-list-${slug}-${pageNumber}`, api => api.GET('/api/page/list', {
      params: { query: { category_slug: slug, page: pageNumber, row: feedRow } },
    }))
  : null
// ?page=9999 у рубрики — такой страницы ленты нет: 404, а не пустая страница с кодом 200
if (feed && pageNumber > 1 && !feed.items.length) {
  throw createError({ statusCode: 404, message: 'Страница не найдена', fatal: true })
}
if (category) {
  usePageSeo({
    title: category.seo_title,
    description: category.seo_description,
    path: feedPath(route.path, pageNumber),
    isIndexed: category.is_indexed,
  })
}
else if (page) {
  usePageSeo({
    title: page.seo_title,
    description: page.seo_description,
    path: page.path,
    image: page.cover?.url,
    isIndexed: page.is_indexed,
  })
}
</script>

<template>
  <PageBlog
    v-if="category && feed"
    :title="category.name" :description="category.description" :result="feed" :page="pageNumber" :row="feedRow"
  />
  <PageArticle v-else-if="page" :page="page" />
</template>
