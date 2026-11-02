<template>
  <UHeader title="Демо-сайт">
    <template #right>
      <UButton to="/blog" label="Блог" variant="ghost" color="neutral" />
      <UButton to="/lk" label="Кабинет" variant="ghost" />
      <UButton to="/login" label="Войти" />
    </template>
  </UHeader>
  <UMain>
    <UContainer class="py-10">
      <slot />
    </UContainer>
  </UMain>
  <UFooter>
    <template #left>
      <nav aria-label="Документы" class="flex flex-wrap gap-4 text-sm">
        <ULink to="/privacy">Политика обработки данных</ULink>
        <ULink to="/consent">Согласие на обработку данных</ULink>
      </nav>
    </template>
  </UFooter>
</template>
