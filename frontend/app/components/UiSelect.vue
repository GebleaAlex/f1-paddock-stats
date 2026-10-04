<script setup lang="ts">
// The site's dropdown. A button that shows "Label: value", a popover list with a check on the selected option,
// keyboard support (arrows, Enter, Escape, type to search), a search box for long lists, and a bottom sheet on
// phones. Native <select> is never used: the OS draws it and it ignores the theme.
export interface SelectOption {
  value: string
  label: string
  sub?: string
  group?: string
  swatch?: string
}

const props = withDefaults(
  defineProps<{ modelValue: string; options: SelectOption[]; label?: string; searchable?: boolean; block?: boolean }>(),
  { label: undefined, searchable: undefined, block: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const query = ref('')
const active = ref(0)
const root = ref<HTMLElement | null>(null)
const list = ref<HTMLElement | null>(null)
const search = ref<HTMLInputElement | null>(null)
const id = useId()

const current = computed(() => props.options.find((o) => o.value === props.modelValue))
const canSearch = computed(() => props.searchable ?? props.options.length > 10)
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q ? props.options.filter((o) => `${o.label} ${o.sub ?? ''}`.toLowerCase().includes(q)) : props.options
})

async function show() {
  open.value = true
  query.value = ''
  active.value = Math.max(0, filtered.value.findIndex((o) => o.value === props.modelValue))
  await nextTick()
  if (canSearch.value) search.value?.focus()
  else list.value?.focus()
  scrollActive()
}
function hide(refocus = true) {
  open.value = false
  if (refocus) root.value?.querySelector<HTMLButtonElement>('.trigger')?.focus()
}
function pick(o: SelectOption | undefined) {
  if (!o) return
  emit('update:modelValue', o.value)
  hide()
}
function scrollActive() {
  nextTick(() => list.value?.querySelector('.on-active')?.scrollIntoView({ block: 'nearest' }))
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    active.value = Math.min(active.value + 1, filtered.value.length - 1)
    scrollActive()
  } else if (e.key === 'ArrowUp') {
    active.value = Math.max(active.value - 1, 0)
    scrollActive()
  } else if (e.key === 'Enter') {
    pick(filtered.value[active.value])
  } else if (e.key === 'Escape' || e.key === 'Tab') {
    hide(e.key === 'Escape')
    return
  } else return
  e.preventDefault()
}
watch(query, () => (active.value = 0))

function outside(e: PointerEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) hide(false)
}
onMounted(() => document.addEventListener('pointerdown', outside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))

function groupStart(i: number) {
  const g = filtered.value[i]?.group
  return g && g !== filtered.value[i - 1]?.group ? g : null
}
</script>

<template>
  <div ref="root" class="ui-select" :class="{ block, open }">
    <button
      type="button"
      class="trigger"
      :aria-haspopup="'listbox'"
      :aria-expanded="open"
      :aria-controls="id"
      @click="open ? hide() : show()"
      @keydown.down.prevent="show"
    >
      <span v-if="current?.swatch" class="swatch" :style="{ background: current.swatch }" />
      <span class="text">
        <span v-if="label" class="prefix">{{ label }}:</span>
        {{ current?.label ?? 'Choose…' }}
      </span>
      <svg class="chev" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
    <Transition name="pop">
      <div v-if="open" class="layer" @click.self="hide()">
        <div class="pop" role="presentation" @keydown="onKey">
          <div class="sheet-head">
            <span class="grabber" />
            <b v-if="label">{{ label }}</b>
          </div>
          <div v-if="canSearch" class="search">
            <input ref="search" v-model="query" type="search" placeholder="Search" :aria-label="`Search ${label ?? 'options'}`" aria-autocomplete="list" :aria-controls="id">
          </div>
          <ul :id="id" ref="list" class="options" role="listbox" tabindex="-1" :aria-label="label">
            <template v-for="(o, i) in filtered" :key="o.value">
              <li v-if="groupStart(i)" class="group" role="presentation">{{ groupStart(i) }}</li>
              <li
                role="option"
                :aria-selected="o.value === modelValue"
                :class="{ 'on-active': i === active, selected: o.value === modelValue }"
                @click="pick(o)"
                @mousemove="active = i"
              >
                <span v-if="o.swatch" class="swatch" :style="{ background: o.swatch }" />
                <span class="grow">
                  <span class="opt-label">{{ o.label }}</span>
                  <span v-if="o.sub" class="opt-sub">{{ o.sub }}</span>
                </span>
                <svg v-if="o.value === modelValue" class="check" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /></svg>
              </li>
            </template>
            <li v-if="!filtered.length" class="none">Nothing matches.</li>
          </ul>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ui-select {
  position: relative;
  display: inline-block;
  max-width: 100%;
}
.ui-select.block {
  display: block;
}
.trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  width: 100%;
  padding: 0 10px 0 12px;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.trigger:hover {
  background: var(--surface-2);
}
.open .trigger {
  border-color: var(--accent);
}
.text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.prefix {
  color: var(--muted);
  font-weight: 500;
}
.chev {
  color: var(--muted);
  flex: none;
  transition: transform 0.15s;
}
.open .chev {
  transform: rotate(180deg);
}
.layer {
  position: absolute;
  z-index: 60;
  top: calc(100% + 6px);
  left: 0;
}
.pop {
  min-width: max(100%, 220px);
  width: max-content;
  max-width: min(360px, 90vw);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.ui-select.block .layer,
.ui-select.block .pop {
  width: 100%;
}
.sheet-head {
  display: none;
}
.search {
  padding: 8px;
  border-bottom: 1px solid var(--border);
}
.search input {
  width: 100%;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  padding: 0 10px;
  outline: none;
}
.search input:focus {
  border-color: var(--accent);
}
.options {
  list-style: none;
  margin: 0;
  padding: 6px;
  max-height: 320px;
  overflow-y: auto;
  outline: none;
}
.options li[role='option'] {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  min-height: 38px;
}
.options li.on-active {
  background: var(--surface-2);
}
.options li.selected {
  font-weight: 600;
}
.opt-label {
  display: block;
}
.opt-sub {
  display: block;
  font-size: 12px;
  color: var(--muted);
  font-weight: 450;
}
.check {
  color: var(--accent);
  flex: none;
}
.group {
  padding: 10px 10px 4px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.none {
  padding: 12px;
  color: var(--muted);
  font-size: 13px;
}
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Phones: the list becomes a bottom sheet over a dimmed page. */
@media (max-width: 640px) {
  .layer {
    position: fixed;
    inset: 0;
    top: 0;
    background: rgba(8, 10, 14, 0.45);
    display: flex;
    align-items: flex-end;
  }
  .pop,
  .ui-select.block .pop {
    width: 100%;
    max-width: none;
    border-radius: 18px 18px 0 0;
    padding-bottom: env(safe-area-inset-bottom);
  }
  .sheet-head {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 8px 16px 4px;
  }
  .grabber {
    width: 40px;
    height: 4px;
    border-radius: 2px;
    background: var(--surface-3);
  }
  .options {
    max-height: 60vh;
  }
  .options li[role='option'] {
    min-height: 46px;
    font-size: 15px;
  }
  .pop-enter-from,
  .pop-leave-to {
    opacity: 0;
    transform: none;
  }
  .pop-enter-from .pop,
  .pop-leave-to .pop {
    transform: translateY(24px);
  }
}
</style>
