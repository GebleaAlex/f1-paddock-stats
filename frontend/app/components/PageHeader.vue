<script setup lang="ts">
// Page title block: breadcrumbs (or a short eyebrow), the title, one line of context, and actions on the right.
// On phones the actions drop below the title and share the width.
defineProps<{ title: string; eyebrow?: string; sub?: string; crumbs?: { to?: string; label: string }[] }>()
</script>

<template>
  <header class="page-header">
    <div class="grow">
      <nav v-if="crumbs?.length" class="crumbs" aria-label="Breadcrumb">
        <template v-for="(c, i) in crumbs" :key="i">
          <NuxtLink v-if="c.to" :to="c.to">{{ c.label }}</NuxtLink>
          <span v-else>{{ c.label }}</span>
          <span v-if="i < crumbs.length - 1" class="sep" aria-hidden="true">/</span>
        </template>
      </nav>
      <div v-else-if="eyebrow || $slots.eyebrow" class="eyebrow"><slot name="eyebrow">{{ eyebrow }}</slot></div>
      <h1>{{ title }}</h1>
      <p v-if="sub || $slots.sub" class="sub"><slot name="sub">{{ sub }}</slot></p>
    </div>
    <div v-if="$slots.default" class="actions"><slot /></div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: var(--gap);
}
.page-header > .grow {
  flex: 1 1 340px;
}
.eyebrow {
  margin-bottom: 6px;
}
.sub {
  margin-top: 6px;
  color: var(--ink-2);
  max-width: 80ch;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 640px) {
  h1 {
    font-size: 25px;
  }
  .actions {
    width: 100%;
  }
  .actions > :deep(*) {
    flex: 1 1 0;
  }
  .actions > :deep(.btn),
  .actions > :deep(a > .btn) {
    width: 100%;
  }
}
</style>
