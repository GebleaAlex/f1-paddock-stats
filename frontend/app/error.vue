<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const notFound = computed(() => props.error.statusCode === 404)
useSeoMeta({ title: () => (notFound.value ? 'Not found' : 'Something went wrong') })
</script>

<template>
  <div class="page">
    <div class="box">
      <div class="eyebrow">{{ error.statusCode }}</div>
      <h1>{{ notFound ? 'That page is not in the history books.' : 'Something went wrong.' }}</h1>
      <p class="ink-2">{{ notFound ? error.statusMessage || 'The link may be mistyped, or the race has not happened yet.' : 'Please try again in a moment.' }}</p>
      <div class="row wrap">
        <button class="btn primary" @click="clearError({ redirect: '/' })">Go to the home page</button>
        <button class="btn" @click="clearError({ redirect: '/seasons' })">Browse seasons</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--page);
}
.box {
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
