<script setup lang="ts">
// Ловушка для ботов: поле «website» за краем экрана. Человек его не видит, по Tab на него не попасть,
// экранный диктор его пропускает (aria-hidden), браузер не автозаполняет. Бот заполняет всё подряд —
// и его заявка молча уходит в спам. Имя выбрано заманчивое для бота; в API значение уходит в leave_empty
const value = defineModel<string>({ required: true })
</script>

<template>
  <div aria-hidden="true" class="absolute -left-[9999px]">
    <input v-model="value" name="website" type="text" tabindex="-1" autocomplete="off">
  </div>
</template>
