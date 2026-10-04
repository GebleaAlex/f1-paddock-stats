<script setup lang="ts">
const route = useRoute()
const { mode, toggle } = useTheme()
// ?embed=<chart id>: the page is shown inside someone else's site, with only that chart and a credit link.
const embed = computed(() => typeof route.query.embed === 'string' && route.query.embed !== '')
const fullPage = computed(() => route.fullPath.replace(/([?&])embed=[^&]*&?/, '$1').replace(/[?&]$/, ''))
const menu = ref(false)

const NAV = [
  { to: '/seasons', label: 'Seasons', hint: 'Standings, races, what-if points' },
  { to: '/drivers', label: 'Drivers', hint: 'Every driver since 1950' },
  { to: '/constructors', label: 'Teams', hint: 'Constructors and lineages' },
  { to: '/circuits', label: 'Circuits', hint: 'Layouts, winners, lap records' },
  { to: '/teammates', label: 'Teammates', hint: 'Head-to-head duels' },
  { to: '/compare', label: 'Compare', hint: 'Up to four careers' },
  { to: '/ratings', label: 'Ratings', hint: 'Drivers across eras' },
  { to: '/explore', label: 'Explore', hint: 'Ask your own questions' },
  { to: '/records', label: 'Records', hint: 'All-time leaderboards' },
]
// Section match on the first path segment, so /races/... belongs to Seasons.
const section = computed(() => {
  const first = route.path.split('/')[1] ?? ''
  return first === 'races' ? '/seasons' : `/${first}`
})
watch(() => route.fullPath, () => (menu.value = false))
// Close the phone menu with Escape and keep the page behind it from scrolling.
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') menu.value = false
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
watch(menu, (open) => {
  if (import.meta.client) document.documentElement.style.overflow = open ? 'hidden' : ''
})

useHead({
  // Apply a stored theme before the first paint so dark-mode visitors never see a light flash.
  script: [
    {
      innerHTML:
        "try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}",
      tagPosition: 'head',
    },
  ],
})
useSeoMeta({
  description:
    'Formula 1 statistics from 1950 to today: seasons, races, drivers, teams, circuits, lap charts and teammate head-to-heads. Free and open source.',
})
</script>

<template>
  <div v-if="embed" class="embed-shell">
    <NuxtPage :page-key="(r) => r.path" />
    <a class="embed-credit small" :href="fullPage" target="_blank" rel="noopener">Paddock Stats · open the full page</a>
  </div>
  <div v-else class="shell">
    <NuxtLoadingIndicator color="var(--accent)" :height="2" :throttle="150" />
    <a class="skip" href="#main">Skip to content</a>
    <header class="top">
      <div class="container bar">
        <NuxtLink to="/" class="brand" aria-label="Paddock Stats home">
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <rect width="28" height="28" rx="8" fill="var(--accent)" />
            <path d="M8 21V7h6.5a4.5 4.5 0 0 1 0 9H8" fill="none" stroke="#fff" stroke-width="2.6" stroke-linejoin="round" />
            <path d="M15 21h5" stroke="#fff" stroke-width="2.6" stroke-linecap="round" />
          </svg>
          <span>Paddock Stats</span>
        </NuxtLink>
        <nav class="nav" aria-label="Main">
          <NuxtLink v-for="n in NAV" :key="n.to" :to="n.to" :class="{ on: section === n.to }">{{ n.label }}</NuxtLink>
        </nav>
        <div class="row tools">
          <SearchBox />
          <button class="btn ghost icon" type="button" aria-label="Switch between light and dark theme" @click="toggle">
            <ClientOnly><Icon :name="mode === 'dark' ? 'sun' : 'moon'" /><template #fallback><Icon name="moon" /></template></ClientOnly>
          </button>
          <button class="btn ghost icon menu-btn" type="button" aria-label="Menu" :aria-expanded="menu" @click="menu = !menu">
            <Icon :name="menu ? 'close' : 'menu'" />
          </button>
        </div>
      </div>
      <Transition name="menu">
        <div v-if="menu" class="menu-layer" @click.self="menu = false">
          <nav class="mobile-nav container" aria-label="Main">
            <NuxtLink v-for="n in NAV" :key="n.to" :to="n.to" :class="{ on: section === n.to }">
              <b>{{ n.label }}</b>
              <span class="small muted">{{ n.hint }}</span>
            </NuxtLink>
            <NuxtLink to="/about" class="about" :class="{ on: section === '/about' }">
              <b>About and data</b>
              <span class="small muted">Sources, licences and how the numbers are made</span>
            </NuxtLink>
          </nav>
        </div>
      </Transition>
    </header>

    <main id="main" class="container main">
      <!-- Remount on a new path (another race or driver), not on query changes (tabs, filters). -->
      <NuxtPage :page-key="(r) => r.path" />
    </main>

    <footer class="foot">
      <div class="container foot-inner small muted">
        <nav class="foot-nav" aria-label="Footer">
          <NuxtLink v-for="n in NAV" :key="n.to" :to="n.to">{{ n.label }}</NuxtLink>
          <NuxtLink to="/eras">Regulation eras</NuxtLink>
          <NuxtLink to="/about">About and data</NuxtLink>
        </nav>
        <p>
          Paddock Stats is unofficial and is not associated in any way with the Formula 1 companies. F1, FORMULA ONE,
          FORMULA 1, FIA FORMULA ONE WORLD CHAMPIONSHIP, GRAND PRIX and related marks are trade marks of Formula One
          Licensing B.V.
        </p>
        <p>
          Data: <a class="link" href="https://github.com/f1db/f1db" rel="noopener">f1db</a> (CC BY 4.0) and
          <a class="link" href="https://github.com/jolpica/jolpica-f1" rel="noopener">Jolpica-F1</a> (CC BY-NC-SA 4.0).
          <NuxtLink class="link" to="/about">About, sources and licences</NuxtLink>. Free, non-commercial and open source.
        </p>
        <p>
          Created by Alex Geblea. The code is
          <a class="link" href="https://github.com/GebleaAlex/Formula-1-F1-Paddock-Stats" rel="noopener">on GitHub</a>
          under the Apache License 2.0.
        </p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.embed-shell {
  padding: 12px;
  background: var(--page);
}
.embed-credit {
  display: block;
  margin-top: 8px;
  text-align: right;
  color: var(--muted);
}
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.top {
  position: sticky;
  top: 0;
  z-index: 50;
  background: color-mix(in srgb, var(--page) 88%, transparent);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--border);
}
.bar {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 60px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 750;
  font-size: 16px;
  letter-spacing: -0.01em;
  white-space: nowrap;
}
.nav {
  display: flex;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.nav a,
.mobile-nav a {
  padding: 7px 10px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 550;
  color: var(--ink-2);
  white-space: nowrap;
}
.nav a:hover,
.mobile-nav a:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.nav a.on,
.mobile-nav a.on {
  color: var(--ink);
  background: var(--surface-2);
}
.tools {
  margin-left: auto;
}
.menu-btn {
  display: none;
}
.menu-layer {
  position: fixed;
  inset: 60px 0 0;
  background: rgba(8, 10, 14, 0.35);
  z-index: 49;
}
.mobile-nav {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding-top: 12px;
  padding-bottom: 16px;
  background: var(--page);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
}
.mobile-nav a {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
}
.mobile-nav a.on {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.mobile-nav .about {
  grid-column: 1 / -1;
}
@media (max-width: 420px) {
  .mobile-nav {
    grid-template-columns: 1fr;
  }
}
.menu-enter-active,
.menu-leave-active {
  transition: opacity 0.15s ease;
}
.menu-enter-active .mobile-nav,
.menu-leave-active .mobile-nav {
  transition: transform 0.15s ease;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
}
.menu-enter-from .mobile-nav,
.menu-leave-to .mobile-nav {
  transform: translateY(-8px);
}
.skip {
  position: absolute;
  left: 8px;
  top: -40px;
  z-index: 100;
  background: var(--accent);
  color: #fff;
  padding: 8px 12px;
  border-radius: 8px;
}
.skip:focus {
  top: 8px;
}
.foot-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-bottom: 4px;
}
.foot-nav a {
  color: var(--ink-2);
  font-weight: 550;
}
.foot-nav a:hover {
  color: var(--ink);
}
@media (max-width: 1080px) {
  .nav {
    display: none;
  }
  .menu-btn {
    display: inline-flex;
  }
}
.main {
  flex: 1;
  padding-top: 28px;
  padding-bottom: 56px;
}
.foot {
  border-top: 1px solid var(--border);
  padding: 24px 0 calc(24px + env(safe-area-inset-bottom));
}
.foot-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: var(--max);
}
.foot-inner p {
  max-width: 100ch;
}
</style>
