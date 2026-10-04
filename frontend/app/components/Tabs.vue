<script setup lang="ts">
// Page tabs. They scroll sideways on narrow screens with faded edges that show there is more, and the selected
// tab is scrolled into view.
const props = defineProps<{ modelValue: string; tabs: { id: string; label: string }[]; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const strip = ref<HTMLElement | null>(null)
const fadeLeft = ref(false)
const fadeRight = ref(false)

function measure() {
  const el = strip.value
  if (!el) return
  fadeLeft.value = el.scrollLeft > 4
  fadeRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}
function reveal() {
  nextTick(() => {
    strip.value?.querySelector<HTMLElement>('.on')?.scrollIntoView({ block: 'nearest', inline: 'center' })
    measure()
  })
}
function onKey(e: KeyboardEvent) {
  const i = props.tabs.findIndex((t) => t.id === props.modelValue)
  const next = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : -1
  if (next >= 0 && next < props.tabs.length) {
    emit('update:modelValue', props.tabs[next]!.id)
    nextTick(() => strip.value?.querySelector<HTMLElement>('.on')?.focus())
  }
}
onMounted(() => {
  reveal()
  window.addEventListener('resize', measure)
})
onBeforeUnmount(() => window.removeEventListener('resize', measure))
watch(() => props.modelValue, reveal)
</script>

<template>
  <div class="tabs-wrap" :class="{ 'fade-l': fadeLeft, 'fade-r': fadeRight }">
    <div ref="strip" class="tabs" role="tablist" :aria-label="label" @scroll.passive="measure" @keydown="onKey">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        role="tab"
        :aria-selected="t.id === modelValue"
        :tabindex="t.id === modelValue ? 0 : -1"
        :class="{ on: t.id === modelValue }"
        @click="emit('update:modelValue', t.id)"
      >
        {{ t.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.tabs-wrap {
  position: relative;
}
.tabs-wrap::before,
.tabs-wrap::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 1px;
  width: 32px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 1;
}
.tabs-wrap::before {
  left: 0;
  background: linear-gradient(90deg, var(--page), transparent);
}
.tabs-wrap::after {
  right: 0;
  background: linear-gradient(270deg, var(--page), transparent);
}
.fade-l::before,
.fade-r::after {
  opacity: 1;
}
.tabs {
  scroll-behavior: smooth;
}
</style>
