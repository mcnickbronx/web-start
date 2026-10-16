<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { components } from '#api-types'

definePageMeta({ layout: 'lk', middleware: 'auth' })
type Row = components['schemas']['PageListOut']

const api = useApi()
const auth = useAuth()
await auth.loadMe()

const search = ref('')
const searchDebounced = ref('')
let searchTimer: ReturnType<typeof setTimeout>
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (searchDebounced.value = value), 400)
})
const categorySlug = ref('all')
const sort = ref('-date_published')
const page = ref(1)
const ROW = 10

const { data: categoryList } = await useAsyncData('categories', async () => (await apiRequest(api.GET('/api/page/category/info'))).data ?? [])
const categoryItemList = computed(() => [{ label: 'Все рубрики', value: 'all' }, ...(categoryList.value ?? []).map(item => ({ label: item.name, value: item.slug }))])
const sortItemList = [{ label: 'Сначала новые', value: '-date_published' }, { label: 'Сначала старые', value: 'date_published' }, { label: 'По заголовку', value: 'title' }]

watch([searchDebounced, categorySlug, sort], () => (page.value = 1))
const { data: result, status } = await useAsyncData('pages', () => apiRequest(api.GET('/api/page/list', { params: { query: {
  page: page.value, row: ROW, sort: sort.value,
  search: searchDebounced.value || undefined,
  category_slug: categorySlug.value === 'all' ? undefined : categorySlug.value,
} } })), { watch: [page, searchDebounced, categorySlug, sort] })

const columnList: TableColumn<Row>[] = [
  { accessorKey: 'row_number', header: '№' },
  { accessorKey: 'title', header: 'Заголовок' },
  { accessorKey: 'category.name', header: 'Рубрика' },
  { accessorKey: 'date_published', header: 'Опубликовано', cell: ({ row }) => new Date(row.original.date_published ?? '').toLocaleDateString('ru-RU') },
]
</script>

<template>
  <UDashboardPanel>
    <template #header>
      <UDashboardNavbar title="Статьи" />
      <UDashboardToolbar>
        <UInput v-model="search" icon="i-lucide-search" placeholder="Поиск по заголовку и анонсу" class="w-72" />
        <USelect v-model="categorySlug" :items="categoryItemList" class="w-44" />
        <USelect v-model="sort" :items="sortItemList" class="w-44" />
      </UDashboardToolbar>
    </template>
    <template #body>
      <UAlert v-if="result?.error" color="error" :title="result.error.message" />
      <UTable :data="result?.data?.items ?? []" :columns="columnList" :loading="status === 'pending'" empty="Ничего не найдено" />
      <div class="flex items-center justify-between pt-4 text-sm text-muted">
        <span>Всего: {{ result?.data?.total.count ?? 0 }}</span>
        <UPagination v-model:page="page" :total="result?.data?.total.count ?? 0" :items-per-page="ROW" />
      </div>
    </template>
  </UDashboardPanel>
</template>
