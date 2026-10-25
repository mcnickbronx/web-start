/**
 * SEO любой страницы — статьи, рубрики, каталога, карточки товара, входа: заголовок, описание, canonical
 * и Open Graph, `noindex`. Адрес — страница без параметров (`path` — если нужен другой).
 * Номер страницы ленты — `page: parsePageNumber(route.query.page)`.
 */
export function useSeo(seo: { title: string, description?: string, path?: string, page?: number, image?: string | null, isIndexed?: boolean }) {
  const { siteUrl } = useRuntimeConfig().public
  const origin = siteUrl || useRequestURL().origin
  const url = canonicalUrl(origin, seo.path ?? useRoute().path, seo.page)
  useSeoMeta({
    title: seo.title,
    description: seo.description,
    ogTitle: seo.title,
    ogDescription: seo.description,
    ogUrl: url,
    ogImage: seo.image ? new URL(seo.image, origin).href : undefined,
    robots: seo.isIndexed === false ? 'noindex' : undefined,
  })
  useHead({ link: [{ rel: 'canonical', href: url }] })
}
