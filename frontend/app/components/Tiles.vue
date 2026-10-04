<template>
  <div class="tiles"><slot /></div>
</template>

<style scoped>
/* Tiles share each row evenly; a short last row stretches instead of leaving a gap. */
.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.tiles > :deep(*) {
  flex: 1 1 150px;
  min-width: 0;
}
@media (max-width: 640px) {
  .tiles {
    gap: 10px;
  }
  .tiles > :deep(*) {
    flex-basis: calc(50% - 5px);
  }
}
</style>
