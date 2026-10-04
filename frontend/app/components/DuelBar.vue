<script setup lang="ts">
// Head-to-head count as a split bar: the left part is this driver's wins, the right part the teammate's.
const props = defineProps<{ won: number; lost: number }>()
const share = computed(() => (props.won + props.lost ? (props.won / (props.won + props.lost)) * 100 : 50))
</script>

<template>
  <div v-if="won + lost === 0" class="duel none" title="No comparable races">–</div>
  <div v-else class="duel" :title="`${won} to ${lost}`" role="img" :aria-label="`${won} to ${lost}`">
    <b class="num">{{ won }}</b>
    <span class="bar"><span class="me" :style="{ width: `${share}%` }" /></span>
    <span class="num muted">{{ lost }}</span>
  </div>
</template>

<style scoped>
.duel {
  display: grid;
  grid-template-columns: 26px 72px 26px;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  justify-content: center;
}
.duel b {
  text-align: right;
}
.bar {
  height: 8px;
  border-radius: 4px;
  background: var(--surface-3);
  overflow: hidden;
  display: flex;
}
.me {
  background: var(--series-1);
  border-right: 2px solid var(--surface);
}
.duel.none {
  display: block;
  text-align: center;
  color: var(--muted);
}
@media (max-width: 640px) {
  .duel {
    grid-template-columns: 22px 44px 22px;
    gap: 4px;
  }
}
</style>
