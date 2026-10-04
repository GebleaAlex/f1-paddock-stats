<script setup lang="ts">
// A short list of mutually exclusive options. Shown as a segmented control when there is room, and as a
// dropdown (UiSelect) on phones or when there are too many options to sit in one row.
import type { SelectOption } from './UiSelect.vue'

const props = withDefaults(
  defineProps<{ modelValue: string; options: SelectOption[]; label: string; inlineMax?: number; collapse?: 'sm' | 'md' | 'always' }>(),
  { inlineMax: 6, collapse: 'sm' },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const mode = computed(() => (props.options.length > props.inlineMax ? 'always' : props.collapse))
const value = computed({ get: () => props.modelValue, set: (v: string) => emit('update:modelValue', v) })
</script>

<template>
  <div class="ui-choice" :class="`collapse-${mode}`">
    <div v-if="mode !== 'always'" class="segmented seg" role="radiogroup" :aria-label="label">
      <button
        v-for="o in options"
        :key="o.value"
        type="button"
        role="radio"
        :aria-checked="o.value === modelValue"
        :class="{ on: o.value === modelValue }"
        @click="value = o.value"
      >
        {{ o.label }}
      </button>
    </div>
    <UiSelect v-model="value" class="sel" :options="options" :label="label" />
  </div>
</template>

<style scoped>
.ui-choice {
  display: inline-flex;
  max-width: 100%;
}
.collapse-always .seg {
  display: none;
}
.collapse-sm .sel,
.collapse-md .sel {
  display: none;
}
@media (max-width: 640px) {
  .collapse-sm .seg {
    display: none;
  }
  .collapse-sm .sel {
    display: inline-block;
  }
}
@media (max-width: 900px) {
  .collapse-md .seg {
    display: none;
  }
  .collapse-md .sel {
    display: inline-block;
  }
}
@media (max-width: 640px) {
  .ui-choice {
    flex: 1 1 auto;
  }
  .ui-choice :deep(.ui-select) {
    width: 100%;
  }
}
</style>
