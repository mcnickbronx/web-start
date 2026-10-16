/**
 * Запоминает, откуда человек пришёл на сайт, — при каждой загрузке сайта (не при переходах
 * внутри него). Заявка потом отправит это в visit. localStorage недоступен (приватный
 * режим, запрет браузера) — источник просто не запомнится, заявке это не мешает.
 */
export default defineNuxtPlugin(() => {
  try {
    const next = buildVisit(document.referrer, location.pathname + location.search, location.hostname)
    const stored = JSON.parse(localStorage.getItem(VISIT_KEY) ?? 'null')
    if (shouldReplaceVisit(stored, next, Date.now())) {
      localStorage.setItem(VISIT_KEY, JSON.stringify({ ...next, date: Date.now() }))
    }
  }
  catch { /* см. выше */ }
})
