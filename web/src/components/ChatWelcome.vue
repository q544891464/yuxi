<template>
  <section class="chat-welcome" :aria-label="`${agent?.name || '数字员工'}欢迎页`">
    <header class="welcome-header">
      <FallbackAvatar
        :src="agent?.icon || ''"
        :default-src="getDefaultEmployeePortrait(agent)"
        :name="agent?.name || '数字员工'"
        :seed="agent?.slug || agent?.id"
        kind="agent"
        :size="56"
        shape="rounded"
      />
      <div>
        <p class="welcome-eyebrow">开始一项任务</p>
        <h1>{{ agent?.name || '选择数字员工' }}</h1>
        <p class="welcome-description">{{ employeeTaskPurpose(agent) }}</p>
      </div>
    </header>
    <ol class="welcome-steps" aria-label="首次任务步骤">
      <li>选择示例或描述目标</li>
      <li>补充材料和要求</li>
      <li>检查后点击发送</li>
    </ol>
    <slot name="skill-description"></slot>
    <p v-if="loading" class="welcome-note" role="status">正在核对员工配置，请稍候…</p>
    <template v-else>
      <section v-if="guide.examples.length" class="starter-tasks" aria-label="任务示例">
        <article v-for="example in guide.examples" :key="example.id" class="starter-task">
          <h2>{{ example.title }}</h2>
          <p><strong>准备材料</strong>{{ example.material }}</p>
          <p><strong>预期结果</strong>{{ example.result }}</p>
          <a-button @click="$emit('preview-task', example.id)">预览示例</a-button>
        </article>
      </section>
      <p class="welcome-note" role="status">{{ guide.notice }}</p>
      <router-link v-if="!agent" to="/employees">选择数字员工</router-link>
    </template>
  </section>
</template>

<script setup>
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'
import { getDefaultEmployeePortrait } from '@/utils/employeePortraits'
import { employeeTaskPurpose } from '@/utils/employeeTaskGuidance'

defineProps({
  agent: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  guide: {
    type: Object,
    default: () => ({ examples: [], notice: '说明任务目标、已有材料和期望结果。' })
  }
})
defineEmits(['preview-task'])
</script>

<style lang="less" scoped>
.chat-welcome {
  color: var(--color-text);
  padding-block: 20px 12px;
}
.welcome-header {
  display: flex;
  align-items: center;
  gap: 16px;
}
.welcome-header > div {
  min-width: 0;
}
.welcome-eyebrow {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
h1 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text);
  overflow-wrap: anywhere;
}
.welcome-description {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.welcome-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  padding-left: 20px;
  margin: 20px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.starter-tasks {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.starter-task {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 16px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
}
.starter-task h2 {
  font-size: 16px;
  margin: 0 0 12px;
  color: var(--color-text);
}
.starter-task p {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.starter-task strong {
  display: block;
  color: var(--color-text);
  font-weight: 500;
  margin-bottom: 2px;
}
.starter-task .ant-btn {
  margin-top: auto;
}
.welcome-note {
  margin: 12px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
@media (max-width: 640px) {
  .starter-tasks {
    grid-template-columns: 1fr;
  }
  .welcome-steps {
    flex-direction: column;
    gap: 6px;
  }
  .starter-task .ant-btn {
    min-height: 40px;
  }
}
</style>
