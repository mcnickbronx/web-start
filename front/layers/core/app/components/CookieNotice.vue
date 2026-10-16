<script setup lang="ts">
// Уведомление о cookie внизу экрана, пока посетитель не ответит. «Отклонить» выключает Метрику:
// со следующей загрузки страницы она не грузится, переходы и цели не отправляются сразу.
// Ответ помнит браузер. Только в браузере: сервер не знает, отвечал ли посетитель раньше
const { isEnabled, policyUrl } = useAppConfig().cookieNotice
const isVisible = ref(false)

onMounted(() => {
  isVisible.value = isEnabled && !readCookieChoice()
})

function answer(choice: CookieChoice) {
  saveCookieChoice(choice)
  isVisible.value = false
}
</script>

<template>
  <div v-if="isVisible" role="region" aria-label="Уведомление о cookie" class="fixed inset-x-3 bottom-3 z-50 mx-auto flex max-w-4xl flex-col gap-3 rounded-lg border border-default bg-default p-4 text-sm shadow-lg md:flex-row md:items-center">
    <p class="text-muted">
      Мы используем файлы cookie, чтобы улучшить ваш опыт на сайте. Нажимая «Принять», вы соглашаетесь
      с нашей <ULink v-if="policyUrl" :to="policyUrl" target="_blank" class="text-primary underline">политикой конфиденциальности</ULink><template v-else>политикой конфиденциальности</template>.
    </p>
    <div class="flex shrink-0 gap-2 self-end md:self-auto">
      <UButton label="Принять" @click="answer('accepted')" />
      <UButton label="Отклонить" color="neutral" variant="outline" @click="answer('declined')" />
    </div>
  </div>
</template>
