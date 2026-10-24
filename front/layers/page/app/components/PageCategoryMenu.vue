<script setup lang="ts">
import type { NavigationMenuItem } from '#ui/types'

// Рубрики блога: «Все» — общая лента /blog, дальше рубрики в порядке из админки, подрубрики — выпадающим списком.
// Список одного уровня (так устроен UNavigationMenu в строку), поэтому подрубрики подрубрик в меню не попадают
const categoryList = await usePageRequest('page-category-info', api => api.GET('/api/page/category/info'))
const itemList: NavigationMenuItem[] = [
  { label: 'Все', to: '/blog', exact: true },
  ...categoryList.map(category => ({
    label: category.name,
    to: category.path,
    children: category.child_list.map(child => ({ label: child.name, to: child.path })),
  })),
]
</script>

<template>
  <UNavigationMenu :items="itemList" class="mb-8 border-b border-default" />
</template>
