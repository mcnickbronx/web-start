// canonical и Open Graph по умолчанию на каждой странице сайта: адрес без параметров — с метками рекламы
// (utm, yclid) это та же страница, и поисковик не заводит дублей. Сайт — NUXT_PUBLIC_SITE_URL, пусто — из запроса.
// Название сайта и картинка для ссылки в мессенджере — seo в app.config сайта.
// Страница со своим SEO (useSeo слоя core, useSeoMeta сайта) перекрывает умолчание: тег остаётся один
export default defineNuxtPlugin(() => {
  const route = useRoute()
  const { siteUrl } = useRuntimeConfig().public
  const origin = siteUrl || useRequestURL().origin
  const url = computed(() => canonicalUrl(origin, route.path))
  useHead({ link: [{ rel: 'canonical', href: url }] })
  useSeoMeta({ ogUrl: url, ogType: 'website', ogLocale: 'ru_RU', ...ogDefault(origin, useAppConfig().seo) })
})
