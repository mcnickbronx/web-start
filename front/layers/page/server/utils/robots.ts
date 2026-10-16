/** Метки рекламы: страница с ними — та же страница. Clean-param склеивает их у Яндекса, Google строку пропускает */
const CLEAN_PARAM_LIST = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'yclid', 'gclid', '_openstat']

/**
 * robots.txt. Закрытый сайт — запрет целиком. Открытый — служебные адреса мимо поиска (кэш слоя,
 * кабинет слоя user), метки рекламы склеиваются, адрес карты сайта. Скрипты и стили
 * (/_nuxt/) не закрываем: без них поисковик не увидит страницу такой, какой её видит человек.
 */
export function buildRobotsTxt(isIndexed: boolean, siteUrl: string): string {
  if (!isIndexed) {
    return 'User-agent: *\nDisallow: /\n'
  }
  return [
    'User-agent: *',
    'Disallow: /_page-api/',
    'Disallow: /lk',
    `Clean-param: ${CLEAN_PARAM_LIST.join('&')}`,
    '',
    `Sitemap: ${siteUrl}/sitemap.xml`,
    '',
  ].join('\n')
}
