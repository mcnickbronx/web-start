/**
 * SEO страницы сайта: заголовок, описание, canonical и Open Graph, закрытие от индексации.
 * Бэкенд отдаёт SEO-поля уже заполненными — если в админке пусто, там заголовок и анонс.
 */
export function usePageSeo(seo: { title: string, description?: string, path: string, image?: string | null, isIndexed?: boolean }) {
  const { siteUrl } = useRuntimeConfig().public
  const origin = siteUrl || useRequestURL().origin
  const url = new URL(seo.path, origin).href
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
