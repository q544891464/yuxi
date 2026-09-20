<template>
  <a-drawer
    :open="open"
    title="已归档"
    placement="left"
    :width="360"
    class="archived-items-drawer"
    @close="$emit('close')"
  >
    <div v-if="loading" class="archive-state"><Loader2 :size="18" />正在加载...</div>
    <div v-else-if="error" class="archive-state archive-error">
      <span>{{ error }}</span>
      <button type="button" @click="$emit('retry')">重试</button>
    </div>
    <template v-else>
      <section class="archive-section">
        <h3>项目</h3>
        <div v-if="!projects.length" class="archive-empty">暂无已归档项目</div>
        <div v-for="project in projects" :key="project.id" class="archive-row">
          <FolderArchive :size="17" />
          <span :title="project.name">{{ project.name }}</span>
          <button type="button" @click="$emit('restore-project', project.id)">恢复</button>
        </div>
      </section>
      <section class="archive-section">
        <h3>会话</h3>
        <div v-if="!conversations.length" class="archive-empty">暂无已归档会话</div>
        <div v-for="chat in conversations" :key="chat.id" class="archive-row">
          <MessageSquare :size="17" />
          <span :title="chat.title">{{ chat.title || '新的对话' }}</span>
          <button type="button" @click="$emit('restore-chat', chat.id)">恢复</button>
        </div>
      </section>
    </template>
  </a-drawer>
</template>

<script setup>
import { FolderArchive, Loader2, MessageSquare } from '@lucide/vue'

defineProps({
  open: Boolean,
  loading: Boolean,
  error: { type: String, default: '' },
  projects: { type: Array, default: () => [] },
  conversations: { type: Array, default: () => [] }
})

defineEmits(['close', 'retry', 'restore-project', 'restore-chat'])
</script>

<style lang="less" scoped>
.archive-state,
.archive-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 8px;
  color: var(--gray-500);
}
.archive-error {
  flex-direction: column;
  color: var(--color-error-700);
  button {
    border: 0;
    background: transparent;
    color: var(--main-color);
    cursor: pointer;
  }
}
.archive-section + .archive-section {
  margin-top: 24px;
}
.archive-section h3 {
  margin: 0 0 8px;
  color: var(--gray-700);
  font-size: 14px;
}
.archive-row {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 6px 8px;
  border-radius: 8px;
  color: var(--gray-800);
  &:hover {
    background: var(--gray-50);
  }
  > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  > button {
    padding: 4px 8px;
    border: 1px solid var(--main-100);
    border-radius: 6px;
    background: var(--main-10);
    color: var(--main-color);
    cursor: pointer;
  }
}
</style>
