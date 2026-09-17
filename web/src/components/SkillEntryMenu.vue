<template>
  <ul class="skill-entry-menu">
    <li v-for="node in nodes" :key="node.id">
      <div class="skill-entry-row">
        <button
          v-if="node.children?.length"
          type="button"
          class="skill-toggle"
          :aria-label="`${expanded(node.id) ? '收起' : '展开'}${node.label}`"
          :aria-expanded="expanded(node.id)"
          @click="toggle(node.id)"
        >
          <ChevronDown :size="14" :class="{ closed: !expanded(node.id) }" />
        </button>
        <button
          type="button"
          class="skill-entry-label"
          :class="{ selected: selectedId === node.id, group: !!node.children?.length }"
          :disabled="disabled"
          :aria-current="selectedId === node.id ? 'true' : undefined"
          @click="$emit('select', node.id)"
        >
          {{ node.label }}
        </button>
      </div>
      <SkillEntryMenu
        v-if="node.children?.length && expanded(node.id)"
        :nodes="node.children"
        :selected-id="selectedId"
        :disabled="disabled"
        @select="$emit('select', $event)"
      />
    </li>
  </ul>
</template>

<script setup>
import { ref } from 'vue'
import { ChevronDown } from '@lucide/vue'
defineProps({
  nodes: { type: Array, required: true },
  selectedId: { type: String, default: '' },
  disabled: Boolean
})
defineEmits(['select'])
const collapsed = ref(new Set(['case-nature']))
const expanded = (id) => !collapsed.value.has(id)
const toggle = (id) => {
  if (collapsed.value.has(id)) collapsed.value.delete(id)
  else collapsed.value.add(id)
}
</script>

<style scoped>
.skill-entry-menu {
  list-style: none;
  padding: 0;
  margin: 0;
}
.skill-entry-menu .skill-entry-menu {
  margin-left: 16px;
}
.skill-entry-row {
  display: flex;
  align-items: center;
}
.skill-entry-label {
  flex: 1;
  min-width: 0;
  text-align: left;
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
}
.skill-entry-label.group {
  font-weight: 600;
}
.skill-entry-label:hover,
.skill-entry-label.selected {
  background: var(--main-10);
  color: var(--main-color);
}
.skill-entry-label:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.skill-toggle {
  display: grid;
  place-items: center;
  padding: 5px 2px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}
.closed {
  transform: rotate(-90deg);
}
button:focus-visible {
  outline: 2px solid var(--main-color);
  outline-offset: -2px;
}
</style>
