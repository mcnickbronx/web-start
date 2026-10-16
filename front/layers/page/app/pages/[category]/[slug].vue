<script setup lang="ts">
// Статья блога: /рубрика/статья. Слаг уникален на весь сайт, поэтому статья ищется по нему одному,
// а рубрика в адресе сверяется: старый или неверный адрес — постоянный редирект на настоящий.
// Страница пересоздаётся на каждый адрес: переход к другой статье — новый запрос при рендере
definePageMeta({ key: route => route.fullPath })

const route = useRoute()
const slug = String(route.params.slug)
const page = await usePageRequest(`page-detail-${slug}`, api => api.GET('/api/page/detail/{slug}', { params: { path: { slug } } }))
if (page.path !== route.path) {
  // С параметрами: по меткам рекламы (utm, yclid) заявка узнаёт, откуда пришёл посетитель
  await navigateTo({ path: page.path, query: route.query, hash: route.hash }, { redirectCode: 301 })
}
usePageSeo({
  title: page.seo_title,
  description: page.seo_description,
  path: page.path,
  image: page.cover?.url,
  isIndexed: page.is_indexed,
})
</script>

<template>
  <PageArticle :page="page" />
</template>
