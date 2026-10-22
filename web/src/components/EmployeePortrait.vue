<template>
  <img
    :src="failed ? fallback : agent?.icon || fallback"
    :alt="`${agent?.name || '数字员工'}形象`"
    draggable="false"
    @error="failed = true"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getDefaultEmployeePortrait } from '@/utils/employeePortraits'
const props = defineProps({ agent: { type: Object, default: null } })
const fallback = computed(() => getDefaultEmployeePortrait(props.agent))
const failed = ref(false)
watch(
  () => props.agent?.icon,
  () => {
    failed.value = false
  }
)
</script>

<style scoped>
img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: left bottom;
  pointer-events: none;
}
</style>
