<script setup lang="ts">
// The only block type: a title, an optional one-line note, optional controls on the right, then content.
defineProps<{ title?: string; note?: string; flush?: boolean }>()
</script>

<template>
  <section class="panel" :class="{ flush }">
    <div v-if="title || $slots.actions" class="panel-head">
      <div class="head-text">
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="note || $slots.note" class="note"><slot name="note">{{ note }}</slot></p>
      </div>
      <div v-if="$slots.actions" class="row wrap"><slot name="actions" /></div>
    </div>
    <slot />
  </section>
</template>

<style scoped>
/* Title block takes the room it needs; controls sit on the right or wrap below it on narrow panels. */
.head-text {
  flex: 1 1 260px;
  min-width: 0;
}
.note {
  margin-top: 4px;
  color: var(--muted);
  font-size: 13px;
}
</style>
