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
const input = ref<HTMLInputElement | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined

const LABELS: Record<Hit['type'], string> = {
  driver: 'Driver',
  constructor: 'Team',
  circuit: 'Circuit',
  season: 'Season',
}

function href(h: Hit) {
  return { driver: `/drivers/${h.id}`, constructor: `/constructors/${h.id}`, circuit: `/circuits/${h.id}`, season: `/seasons/${h.id}` }[h.type]
}

watch(q, (value) => {
  clearTimeout(timer)
  if (!value.trim()) {
    hits.value = []
    return
  }
  timer = setTimeout(async () => {
    try {
      hits.value = await $fetch<Hit[]>('/api/search', { query: { q: value.trim(), limit: 6 } })
      active.value = 0
    } catch {
      hits.value = []
    }
  }, 120)
})

async function show() {
  open.value = true
  await nextTick()
  input.value?.focus()
}
function hide() {
  open.value = false
  q.value = ''
}
async function go(h: Hit | undefined) {
  if (!h) return
  hide()
  await navigateTo(href(h))
}
function key(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    active.value = Math.min(active.value + 1, hits.value.length - 1)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    active.value = Math.max(active.value - 1, 0)
    e.preventDefault()
  } else if (e.key === 'Enter') {
    go(hits.value[active.value])
  } else if (e.key === 'Escape') {
    hide()
  }
}
function global(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
  if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) {
    e.preventDefault()
    show()
  }
}
onMounted(() => window.addEventListener('keydown', global))
onBeforeUnmount(() => window.removeEventListener('keydown', global))
defineExpose({ show })
</script>

<template>
  <button class="trigger" type="button" aria-label="Search" @click="show">
    <Icon name="search" :size="16" />
    <span class="label">Search drivers, teams, circuits…</span>
    <kbd>/</kbd>
  </button>
  <Teleport to="body">
    <div v-if="open" class="layer" @click.self="hide">
      <div class="dialog" role="dialog" aria-label="Search">
        <div class="field">
          <Icon name="search" />
          <input
            ref="input"
            v-model="q"
            placeholder="Search drivers, teams, circuits or a year"
            aria-label="Search"
            autocomplete="off"
            @keydown="key"
          >
          <button class="btn ghost icon" type="button" aria-label="Close" @click="hide"><Icon name="close" /></button>
        </div>
        <ul v-if="hits.length" class="hits">
          <li v-for="(h, i) in hits" :key="h.type + h.id">
            <NuxtLink :to="href(h)" :class="{ on: i === active }" @click="hide" @mouseenter="active = i">
              <span class="badge">{{ LABELS[h.type] }}</span>
              <span class="grow ellipsis"><b>{{ h.name }}</b></span>
              <span v-if="h.sub" class="muted small ellipsis sub">{{ h.sub }}</span>
            </NuxtLink>
          </li>
        </ul>
        <p v-else-if="q.trim()" class="empty small">Nothing matches “{{ q }}”.</p>
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
