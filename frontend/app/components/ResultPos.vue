<script setup lang="ts">
// Finishing position pill: P1 dark, podium mid, classified neutral, not classified as muted text.
const props = defineProps<{ position: number | null | undefined; text?: string | null }>()
const cls = computed(() => {
  const p = props.position
  if (p == null) return 'out'
  return p === 1 ? 'p1' : p <= 3 ? 'p2' : ''
})
</script>

<template>
  <span class="pos" :class="cls">{{ position ?? text ?? '–' }}</span>
</template>
