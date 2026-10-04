<script setup lang="ts">
// A team name with its colour bar, linking to the team page.
defineProps<{ id: string; name: string; link?: boolean }>()
</script>

<template>
  <span class="team">
    <span class="team-bar" :style="{ background: teamColor(id) }" />
    <NuxtLink v-if="link !== false" :to="`/constructors/${id}`" class="link-plain">{{ name }}</NuxtLink>
    <span v-else>{{ name }}</span>
  </span>
</template>

<style scoped>
.team {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.team-bar {
  height: 14px;
}
.link-plain:hover {
  text-decoration: underline;
}
</style>
