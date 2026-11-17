<script setup lang="ts">
// Global search: drivers, constructors, circuits and seasons. Opens with "/" or Ctrl/Cmd+K.
interface Hit {
  type: 'driver' | 'constructor' | 'circuit' | 'season'
  id: string
  name: string
  sub: string | null
}

const open = ref(false)
const q = ref('')
const hits = ref<Hit[]>([])
const active = ref(0)
const searching = ref(false)
const input = ref<HTMLInputElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const dialog = ref<HTMLElement | null>(null)
const listId = useId()
let timer: ReturnType<typeof setTimeout> | undefined
// Each search gets a number, so a slow answer for "ha" cannot replace the answer for "hamilton".
let searchId = 0
let running: Promise<void> | undefined

const LABELS: Record<Hit['type'], string> = {
  driver: 'Driver',
  constructor: 'Team',
  circuit: 'Circuit',
  season: 'Season',
}

function href(h: Hit) {
  return { driver: `/drivers/${h.id}`, constructor: `/constructors/${h.id}`, circuit: `/circuits/${h.id}`, season: `/seasons/${h.id}` }[h.type]
}

async function run(value: string) {
  const mine = ++searchId
  try {
    const found = await $fetch<Hit[]>('/api/search', { query: { q: value, limit: 6 } })
    if (mine !== searchId) return
    hits.value = found
    active.value = 0
  } catch {
    if (mine === searchId) hits.value = []
  } finally {
    if (mine === searchId) searching.value = false
  }
}
watch(q, (value) => {
  clearTimeout(timer)
  timer = undefined
  const term = value.trim()
  if (!term) {
    searchId++
    searching.value = false
    hits.value = []
    return
  }
  searching.value = true
  timer = setTimeout(() => {
    timer = undefined
    running = run(term)
  }, 120)
})

async function show() {
  open.value = true
  await nextTick()
  input.value?.focus()
}
function hide(refocus = true) {
  if (!open.value) return
  open.value = false
  q.value = ''
  if (refocus) trigger.value?.focus()
}
async function go(h: Hit | undefined) {
  if (!h) return
  hide(false)
  await navigateTo(href(h))
}
/** Enter straight after typing: wait for the answer to what was typed instead of opening a stale first result. */
async function enter() {
  const term = q.value.trim()
  if (!term) return
  if (timer) {
    clearTimeout(timer)
    timer = undefined
    running = run(term)
  }
  if (searching.value) await running
  if (open.value && q.value.trim() === term) go(hits.value[active.value])
}
function move(step: number) {
  if (!hits.value.length) return
  active.value = Math.min(Math.max(active.value + step, 0), hits.value.length - 1)
  nextTick(() => dialog.value?.querySelector('.hits a.on')?.scrollIntoView({ block: 'nearest' }))
}
function key(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    move(1)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    move(-1)
    e.preventDefault()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    enter()
  }
}
/** Escape closes from anywhere in the dialog, and Tab stays inside it instead of wandering into the page behind. */
function dialogKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    hide()
    return
  }
  if (e.key !== 'Tab' || !dialog.value) return
  const items = Array.from(dialog.value.querySelectorAll<HTMLElement>('input, button, a[href]'))
  const first = items[0]
  const last = items[items.length - 1]
  if (!first || !last) return
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}
function global(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  const typing = !!target && (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable)
  if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey)) {
    e.preventDefault()
    show()
  }
}
// The page behind the dialog does not scroll while it is open.
watch(open, (isOpen) => {
  if (import.meta.client) document.documentElement.style.overflow = isOpen ? 'hidden' : ''
})
onMounted(() => window.addEventListener('keydown', global))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', global)
  clearTimeout(timer)
  if (open.value) document.documentElement.style.overflow = ''
})
defineExpose({ show })
</script>

<template>
  <button ref="trigger" class="trigger" type="button" aria-label="Search" aria-haspopup="dialog" @click="show">
    <Icon name="search" :size="16" />
    <span class="label">Search drivers, teams, circuits…</span>
    <kbd>/</kbd>
  </button>
  <Teleport to="body">
    <div v-if="open" class="layer" @click.self="hide()">
      <div ref="dialog" class="dialog" role="dialog" aria-modal="true" aria-label="Search" @keydown="dialogKey">
        <div class="field">
          <Icon name="search" />
          <input
            ref="input"
            v-model="q"
            placeholder="Search drivers, teams, circuits or a year"
            aria-label="Search"
            role="combobox"
            aria-autocomplete="list"
            :aria-expanded="hits.length > 0"
            :aria-controls="listId"
            :aria-activedescendant="hits.length ? `${listId}-${active}` : undefined"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            enterkeyhint="search"
            @keydown="key"
          >
          <button class="btn ghost icon" type="button" aria-label="Close" @click="hide()"><Icon name="close" /></button>
        </div>
        <ul v-if="hits.length" :id="listId" class="hits" role="listbox" aria-label="Results">
          <li v-for="(h, i) in hits" :key="h.type + h.id" role="presentation">
            <NuxtLink :id="`${listId}-${i}`" :to="href(h)" role="option" :aria-selected="i === active" :class="{ on: i === active }" @click="hide(false)" @mouseenter="active = i">
              <span class="badge">{{ LABELS[h.type] }}</span>
              <span class="grow ellipsis"><b>{{ h.name }}</b></span>
              <span v-if="h.sub" class="muted small ellipsis sub">{{ h.sub }}</span>
            </NuxtLink>
          </li>
        </ul>
        <p v-else-if="searching" class="empty small" role="status">Searching…</p>
        <p v-else-if="q.trim()" class="empty small" role="status">Nothing matches “{{ q }}”.</p>
        <p v-else class="empty small">Try “Senna”, “McLaren”, “Monza” or “1988”.</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px 0 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--muted);
  cursor: pointer;
  width: 300px;
  max-width: 100%;
}
.trigger .label {
  flex: 1;
  text-align: left;
  font-size: 13px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
kbd {
  font: 11px var(--mono);
  border: 1px solid var(--border-strong);
  border-radius: 5px;
  padding: 0 5px;
}
@media (max-width: 1360px) {
  .trigger {
    width: 36px;
    padding: 0;
    justify-content: center;
  }
  .trigger .label,
  .trigger kbd {
    display: none;
  }
}
.layer {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(8, 10, 14, 0.4);
  backdrop-filter: blur(2px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 10vh 16px 16px;
}
.dialog {
  width: 100%;
  max-width: 560px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.field {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px 8px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--muted);
}
.field input {
  flex: 1;
  border: 0;
  background: none;
  height: 40px;
  font-size: 16px;
  color: var(--ink);
  outline: none;
  min-width: 0;
}
.hits {
  list-style: none;
  margin: 0;
  padding: 6px;
  max-height: 60vh;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.hits a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  min-height: 44px;
}
.hits a.on {
  background: var(--accent-soft);
}
.hits .badge {
  width: 58px;
  text-align: center;
  flex: none;
}
.sub {
  max-width: 45%;
}
</style>
