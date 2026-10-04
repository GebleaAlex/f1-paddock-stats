<script setup lang="ts">
// What a block says when it has nothing to show: what would appear here, and what to try.
defineProps<{ title: string; text?: string }>()
</script>

<template>
  <div class="empty-state">
    <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 21V4h11l-2 4 2 4H5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
    </svg>
    <b>{{ title }}</b>
    <p v-if="text" class="small muted">{{ text }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 36px 16px;
  text-align: center;
  color: var(--ink-2);
}
.empty-state svg {
  color: var(--axis);
  margin-bottom: 4px;
}
</style>
