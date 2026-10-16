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
</template>
