/** Название сайта и картинка Open Graph по умолчанию — из `seo` в app.config сайта. Пусто — тега нет:
 * своей картинки у движка нет. Картинка — полным адресом от адреса сайта: относительный
 * (`/images/og.png`) мессенджеры не понимают */
export function ogDefault(origin: string, seo: { siteName: string, image: string }) {
  return {
    ogSiteName: seo.siteName || undefined,
    ogImage: seo.image ? new URL(seo.image, origin).href : undefined,
  }
}
