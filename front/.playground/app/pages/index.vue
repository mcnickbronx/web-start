<script setup lang="ts">
const { detail, error, isLoading, isSent, trap, upload, submit, clearFieldError } = useSiteForm('callback')
const fields = reactive({ name: '', phone: '', captcha: '' })

async function onFile(value: File | null | undefined) {
  if (value) await upload(value)
}
</script>

<template>
  <UPageCard title="Заказать звонок" description="Перезвоним в течение рабочего дня" class="mx-auto max-w-md">
    <p v-if="!detail" class="text-muted">{{ error?.message ?? 'Загрузка формы…' }}</p>
    <form v-else class="space-y-4" @submit.prevent="submit(fields)">
      <UFormField label="Имя" :error="error?.fieldMap.name">
        <UInput v-model="fields.name" class="w-full" @update:model-value="clearFieldError('name')" />
      </UFormField>
      <UFormField label="Телефон" :required="detail.required_field_list.includes('phone')" :error="error?.fieldMap.phone">
        <UInput v-model="fields.phone" type="tel" class="w-full" @update:model-value="clearFieldError('phone')" />
      </UFormField>
      <FormTrap v-model="trap" />
      <FormSmartCaptcha
        v-if="detail.captcha_provider === 'yandex'"
        v-model="fields.captcha" :sitekey="detail.captcha_client_key" :form-token="detail.token"
      />
      <UFormField v-if="detail.captcha_question" :label="`Сколько будет ${detail.captcha_question}?`" :error="error?.fieldMap.captcha">
        <UInput v-model="fields.captcha" inputmode="numeric" class="w-24" @update:model-value="clearFieldError('captcha')" />
      </UFormField>
      <UFileUpload v-if="detail.is_file" label="Приложить файл" class="w-full" @update:model-value="onFile" />
      <UButton type="submit" label="Отправить" :loading="isLoading" block />
      <UAlert v-if="isSent" color="success" title="Заявка отправлена" />
      <UAlert v-if="error" color="error" :title="error.message" />
    </form>
  </UPageCard>
</template>
