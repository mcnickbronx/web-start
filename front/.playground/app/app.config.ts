// Адреса документов принадлежат демо-сайту; список дописывается к списку движка ('/')
export default defineAppConfig({
  cookieNotice: { policyUrl: '/privacy' },
  personalData: { consentUrl: '/consent' },
  page: { sitemapPageList: ['/blog', '/privacy', '/consent'] },
})
