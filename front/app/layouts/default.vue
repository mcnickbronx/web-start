<!-- Каркас по умолчанию: сайт кладёт свой app/layouts/default.vue — с шапкой и подвалом -->
<template>
  <UMain>
    <UContainer class="py-10">
      <slot />
    </UContainer>
  </UMain>
</template>
