// Title, description and social preview for a page. The preview image is drawn by the API (/api/og.png) from the
// same facts the page shows, so a shared link always previews what it opens. Every field may be a value or a getter.
type Maybe<T> = T | (() => T)

export interface PageMeta {
  title?: Maybe<string | undefined>
  description?: Maybe<string | undefined>
  eyebrow?: Maybe<string | undefined>
  stats?: Maybe<[string, string | number | null | undefined][] | undefined>
  color?: Maybe<string | null | undefined>
}

export function usePageMeta(meta: PageMeta) {
  const config = useRuntimeConfig()
  const route = useRoute()
  const title = computed(() => toValue(meta.title))
  const description = computed(() => toValue(meta.description))
  const image = computed(() => {
    const q = new URLSearchParams()
    if (title.value) q.set('title', title.value.slice(0, 90))
    const eyebrow = toValue(meta.eyebrow)
    if (eyebrow) q.set('eyebrow', eyebrow.slice(0, 60))
    if (description.value) q.set('sub', description.value.slice(0, 160))
    const stats = (toValue(meta.stats) ?? []).filter(([, v]) => v != null && v !== '').map(([k, v]) => `${k}:${v}`)
    if (stats.length) q.set('stats', stats.slice(0, 4).join('|'))
    const color = toValue(meta.color)
    if (color) q.set('color', color.replace('#', ''))
    return `${config.public.siteUrl}/api/og.png?${q}`
  })
  const fullTitle = computed(() => (title.value ? `${title.value} · Paddock Stats` : 'Paddock Stats'))
  useSeoMeta({
    title: () => title.value,
    description: () => description.value,
    ogTitle: fullTitle,
    ogDescription: () => description.value,
    ogImage: image,
    ogImageWidth: 1200,
    ogImageHeight: 630,
    ogImageAlt: fullTitle,
    ogUrl: () => `${config.public.siteUrl}${route.path}`,
    ogType: 'website',
    ogSiteName: 'Paddock Stats',
    twitterCard: 'summary_large_image',
    twitterTitle: fullTitle,
    twitterDescription: () => description.value,
    twitterImage: image,
  })
}
