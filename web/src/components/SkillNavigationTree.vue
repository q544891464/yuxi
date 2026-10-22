<template>
  <ul class="skill-entry-menu">
    <li v-for="node in nodes" :key="node.id">
      <div class="skill-entry-row">
        <button
          type="button"
          class="skill-entry-label"
          :class="{ selected: selectedId === node.id, group: !!node.children?.length }"
          :aria-expanded="!node.skill && node.children?.length ? expanded(node.id) : undefined"
          :disabled="disabled && !!node.skill"
          :aria-current="selectedId === node.id ? 'true' : undefined"
          @click="
            node.skill ? $emit('select', { ...node.skill, navigationId: node.id }) : toggle(node.id)
          "
        >
          <component
            :is="node.children?.length ? (expanded(node.id) ? FolderOpen : FolderClosed) : FileText"
            :size="14"
            class="entry-icon"
            aria-hidden="true"
          />
          <span class="entry-name" :title="node.name">{{ node.name }}</span>
        </button>
        <button
          v-if="node.children?.length"
          type="button"
          class="skill-toggle"
          :aria-label="`${expanded(node.id) ? '收起' : '展开'}${node.name}`"
          :aria-expanded="expanded(node.id)"
          @click="toggle(node.id)"
        >
          <ChevronDown :size="14" :class="{ closed: !expanded(node.id) }" />
        </button>
      </div>
      <SkillNavigationTree
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
import { ChevronDown, FileText, FolderClosed, FolderOpen } from '@lucide/vue'
defineProps({
  nodes: { type: Array, required: true },
  selectedId: { type: String, default: '' },
  disabled: Boolean
})
defineEmits(['select'])
const collapsed = ref(new Set())
const expanded = (id) => !collapsed.value.has(id)
const toggle = (id) => {
  if (collapsed.value.has(id)) collapsed.value.delete(id)
  else collapsed.value.add(id)
}
</script>

<style lang="less" scoped>
.skill-entry-menu {
  list-style: none;
  padding: 0;
  margin: 0;
}
.skill-entry-menu .skill-entry-menu {
  margin-left: 22px;
}
.skill-entry-row {
  position: relative;
  display: flex;
  align-items: center;
}
.skill-entry-label {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 8px;
  min-width: 0;
  min-height: 32px;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text);
  font-size: 13px;
  line-height: 20px;
  text-align: left;
  cursor: pointer;
}
.skill-entry-label.group {
  padding-right: 30px;
  font-weight: 500;
}
.entry-icon {
  flex: 0 0 14px;
}
.entry-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  position: absolute;
  right: 4px;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 24px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}
.skill-toggle:hover {
  background: var(--gray-100);
}
.closed {
  transform: rotate(-90deg);
}
button:focus-visible {
  outline: 2px solid var(--main-color);
  outline-offset: -2px;
}
@media (hover: none) {
  .skill-entry-label {
    min-height: 40px;
  }
  .skill-toggle {
    height: 36px;
  }
}
</style>
