<template>
  <div v-if="label" class="source">
    <button v-if="reference.file_path && openSource" type="button" @click="openSource(reference)">
      查看原文 · {{ label }}
    </button>
    <span v-else>来源：{{ label }}</span>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
const props = defineProps({ reference: { type: Object, default: null } })
const openSource = inject('openEvidenceReviewSource', null)
const label = computed(() => {
  const ref = props.reference
  if (!ref) return ''
  return [
    ref.document,
    ref.section,
    ref.evidence_id,
    ref.page ? `第 ${ref.page} 页` : '',
    ref.paragraph_id ? `段落 ${ref.paragraph_id}` : '',
    ref.chunk_id ? `片段 ${ref.chunk_id}` : '',
    !ref.document && ref.file_path ? ref.file_path.split('/').pop() : ''
  ]
    .filter(Boolean)
    .join(' · ')
})
</script>

<style scoped>
.source {
  margin-top: 6px;
  font-size: 12px;
  color: var(--gray-600);
  overflow-wrap: anywhere;
}
button {
  border: 0;
  background: transparent;
  color: var(--main-600);
  padding: 0;
  cursor: pointer;
  text-align: left;
}
button:hover {
  text-decoration: underline;
}
</style>
