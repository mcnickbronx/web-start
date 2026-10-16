<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

// Рубрики блога: «Все» — общая лента /blog, дальше рубрики в порядке из админки
const categoryList = await usePageRequest('page-category-info', api => api.GET('/api/page/category/info'))
const itemList: NavigationMenuItem[] = [
  { label: 'Все', to: '/blog', exact: true },
  ...categoryList.map(category => ({ label: category.name, to: category.path })),
]
</script>

<template>
  <UNavigationMenu :items="itemList" class="mb-8 border-b border-default" />
</template>
