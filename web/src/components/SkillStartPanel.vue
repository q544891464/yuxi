<template>
  <section class="skill-start-panel" aria-label="技能说明" aria-live="polite">
    <template v-if="entry">
      <div class="skill-start-heading">
        <h2>{{ entry.label }}</h2>
        <span>{{ projectName ? `当前项目：${projectName}` : '可在输入框上方选择项目' }}</span>
      </div>
      <dl>
        <div>
          <dt>准备材料</dt>
          <dd>{{ entry.inputHint }}</dd>
        </div>
        <div>
          <dt>功能用途与结果</dt>
          <dd>{{ entry.outputHint }}</dd>
        </div>
      </dl>
      <div class="skill-start-actions">
        <button type="button" :disabled="!available || disabled" @click="$emit('upload')">
          <Upload :size="18" />上传材料
        </button>
        <p v-if="available">已引用 {{ entry.skillDisplayName }}。上传后可编辑提示词，点击发送开始使用。</p>
        <p v-else role="status">
          {{ entry.skillDisplayName }} 暂不可用，请检查技能安装、访问权限及当前智能体配置。
        </p>
      </div>
    </template>
    <template v-else>
      <h2><Sparkles :size="18" />选择技能，开始办理</h2>
      <p>从左侧选择业务功能，查看所需材料、上传文件并发送；也可以直接输入问题。</p>
    </template>
  </section>
</template>

<script setup>
import { Upload, Sparkles } from '@lucide/vue'
defineProps({
  entry: { type: Object, default: null },
  available: Boolean,
  disabled: Boolean,
  projectName: { type: String, default: '' }
})
defineEmits(['upload'])
</script>

<style scoped>
.skill-start-panel {
  border: 1px solid var(--gray-150);
  border-radius: 18px;
  padding: 14px 20px;
  background: var(--gray-0);
  color: var(--color-text);
  text-align: left;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 17px;
  color: var(--main-color);
}
.skill-start-heading {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}
.skill-start-heading span,
p {
  color: var(--color-text-secondary);
  font-size: 13px;
}
dl {
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.7;
}
dl > div {
  display: flex;
  gap: 12px;
}
dt {
  flex: 0 0 100px;
  font-weight: 600;
}
dd {
  margin: 0;
}
.skill-start-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
button {
  display: flex;
  gap: 8px;
  align-items: center;
  border: 0;
  border-radius: 9px;
  padding: 9px 18px;
  background: var(--main-color);
  color: var(--gray-0);
  cursor: pointer;
  font-weight: 600;
}
.skill-start-actions p {
  margin: 0;
  flex: 1 1 240px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible {
  outline: 2px solid var(--main-700);
  outline-offset: 3px;
}
p {
  margin: 8px 0 0;
  line-height: 1.6;
}
@media (max-width: 640px) {
  .skill-start-panel {
    padding: 14px;
  }
  dl > div {
    display: block;
    margin-bottom: 8px;
  }
}
</style>
