// Счётчик Яндекс Метрики. Первую страницу счётчик учитывает сам, переходы внутри сайта — вручную:
// иначе Метрика увидит одну страницу за визит. Номер счётчика — NUXT_PUBLIC_METRIKA_ID; пусто — счётчика нет.
// Посетитель отклонил cookie (CookieNotice) — Метрика не грузится
export default defineNuxtPlugin((nuxtApp) => {
  const { counterId } = useMetrika()
  if (!counterId || readCookieChoice() === 'declined') {
    return
  }

  // Очередь вызовов до загрузки tag.js — как в коде счётчика из кабинета Метрики
  type YmQueue = NonNullable<Window['ym']> & { a?: unknown[][], l?: number }
  if (!window.ym) {
    const ym: YmQueue = (...args: unknown[]) => {
      (ym.a ??= []).push(args)
    }
    ym.l = Date.now()
    window.ym = ym
  }
  const script = document.createElement('script')
  script.src = `https://mc.yandex.ru/metrika/tag.js?id=${counterId}`
  script.async = true
  document.head.append(script)
  window.ym!(counterId, 'init', {
    ssr: true, webvisor: true, clickmap: true, ecommerce: 'dataLayer', trackLinks: true, accurateTrackBounce: true,
    referrer: document.referrer, url: location.href,
  })

  // Переход — когда новая страница отрисована (заголовок уже её). Якоря (#tarify) — не новая страница
  const pageUrl = () => location.href.split('#')[0]!
  let urlLast = pageUrl()
  nuxtApp.hook('page:finish', () => {
    const url = pageUrl()
    // Отклонил cookie на этой странице — дальше переходы не отправляем
    if (url !== urlLast && readCookieChoice() !== 'declined') {
      window.ym!(counterId, 'hit', url, { referer: urlLast, title: document.title })
      urlLast = url
    }
  })
})
