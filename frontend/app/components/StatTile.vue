<script setup lang="ts">
import { NuxtLink } from '#components'
defineProps<{ label: string; value: string | number | null | undefined; hint?: string; to?: string }>()
</script>

<template>
  <component :is="to ? NuxtLink : 'div'" :to="to" class="tile" :class="{ clickable: to }">
    <div class="label">{{ label }}</div>
    <div class="value" :class="{ text: typeof value === 'string' && !/^[\d.,%+−-]+$/.test(value) }">{{ value ?? '–' }}</div>
    <div v-if="hint" class="hint">{{ hint }}</div>
  </component>
</template>

<style scoped>
.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  min-width: 0;
  display: block;
}
.tile.clickable:hover {
  border-color: var(--border-strong);
}
.label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 550;
}
.value {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.value.text {
  font-size: 19px;
  line-height: 1.3;
  padding-top: 5px;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.hint {
  font-size: 12px;
  color: var(--ink-2);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 640px) {
  .tile {
    padding: 12px 14px;
  }
  .value {
    font-size: 22px;
  }
  .value.text {
    font-size: 16px;
  }
}
</style>
