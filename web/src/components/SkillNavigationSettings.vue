<template>
  <section class="navigation-settings">
    <h2>侧栏技能</h2>
    <p class="hint">
      配置全平台技能菜单及项目内的新会话入口。删除入口不会删除技能本体，绑定不会改变技能权限。
    </p>
    <a-alert v-if="error" type="error" :message="error" show-icon />
    <a-spin :spinning="loading">
      <div class="toolbar">
        <a-button :disabled="loading || saving" @click="reload">重新加载</a-button>
        <a-button :disabled="!ready || saving" @click="add">添加入口</a-button>
        <a-button type="primary" :loading="saving" :disabled="!ready || loading" @click="save"
          >保存配置</a-button
        >
        <span v-if="dirty" class="hint">有未保存修改</span>
      </div>
      <div v-if="ready" class="editor">
        <div class="entry-list">
          <p v-if="!rows.length" class="hint">暂无入口，点击“添加入口”开始配置。</p>
          <div
            v-for="row in orderedRows"
            :key="row.id"
            class="entry-row"
            :class="{ selected: selectedId === row.id }"
          >
            <button
              class="entry-select"
              :style="{ paddingLeft: `${8 + row.depth * 12}px` }"
              @click="selectedId = row.id"
            >
              {{ row.label || '未命名入口' }}
            </button>
            <button
              :aria-label="`上移${row.label}`"
              :disabled="!canMove(row, -1) || saving"
              @click="moveNavigationRow(rows, row.id, -1)"
            >
              ↑
            </button>
            <button
              :aria-label="`下移${row.label}`"
              :disabled="!canMove(row, 1) || saving"
              @click="moveNavigationRow(rows, row.id, 1)"
            >
              ↓
            </button>
          </div>
        </div>
        <a-form v-if="selected" layout="vertical" class="entry-form" :disabled="saving">
          <a-form-item label="入口中文名称" required
            ><a-input v-model:value="selected.label" :maxlength="60"
          /></a-form-item>
          <a-form-item label="父级入口"
            ><a-select v-model:value="selected.parentId" :options="parentOptions"
          /></a-form-item>
          <a-form-item label="绑定技能" required>
            <a-select
              :value="selected.skillSlug"
              :options="skillOptions"
              show-search
              option-filter-prop="label"
              @change="bindSkill"
            />
            <p class="hint">
              仅列出可访问且已启用的共享技能。未找到时请先在技能管理中安装或共享，并检查智能体是否开放该技能。
            </p>
            <p v-if="!skillOptions.some((s) => s.value === selected.skillSlug)" class="warning">
              当前绑定不可用，请重新选择；也可保留原绑定后继续整理菜单。
            </p>
          </a-form-item>
          <a-form-item label="技能中文显示名" required
            ><a-input v-model:value="selected.skillDisplayName" :maxlength="60"
          /></a-form-item>
          <a-form-item label="准备材料" required
            ><a-textarea v-model:value="selected.inputHint" :rows="2" :maxlength="2000"
          /></a-form-item>
          <a-form-item label="功能用途与结果" required
            ><a-textarea v-model:value="selected.outputHint" :rows="2" :maxlength="2000"
          /></a-form-item>
          <a-form-item label="预设提示词" required
            ><a-textarea v-model:value="selected.presetPrompt" :rows="4" :maxlength="10000" />
            <p class="hint">技能引用由系统自动添加，此处只填写任务指令。</p></a-form-item
          >
          <a-button danger @click="remove">删除此入口</a-button>
        </a-form>
      </div>
    </a-spin>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { listSkills } from '@/apis/skill_api'
import { skillNavigationApi } from '@/apis/skill_navigation_api'
import { useSkillNavigationStore } from '@/stores/skillNavigation'
import { getSkillDisplayName } from '@/utils/skillDisplayName'
import {
  createNavigationEntryId,
  navigationRows,
  navigationTree,
  descendantIds,
  moveNavigationRow
} from '@/utils/skillNavigationEditor'

const store = useSkillNavigationStore()
const rows = ref([])
const skills = ref([])
const selectedId = ref('')
const revision = ref(0)
const saved = ref('[]')
const ready = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const dirty = computed(() => JSON.stringify(rows.value) !== saved.value)
const selected = computed(() => rows.value.find((row) => row.id === selectedId.value))
const orderedRows = computed(() => {
  const visit = (parent, depth) =>
    rows.value
      .filter((row) => row.parentId === parent)
      .flatMap((row) => [{ ...row, depth }, ...visit(row.id, depth + 1)])
  return visit('', 0)
})
const parentOptions = computed(() => {
  const excluded = new Set([selectedId.value, ...descendantIds(rows.value, selectedId.value)])
  return [
    { value: '', label: '顶级入口' },
    ...orderedRows.value
      .filter((row) => !excluded.has(row.id))
      .map((row) => ({ value: row.id, label: `${'　'.repeat(row.depth)}${row.label}` }))
  ]
})
const skillOptions = computed(() =>
  skills.value
    .filter((skill) => skill.enabled !== false)
    .map((skill) => ({
      value: skill.slug,
      label: `${getSkillDisplayName(skill.slug, skill.name)}（${skill.slug}）`
    }))
)
const canMove = (row, direction) => {
  const siblings = rows.value.filter((item) => item.parentId === row.parentId)
  return !!siblings[siblings.findIndex((item) => item.id === row.id) + direction]
}
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [config, response] = await Promise.all([skillNavigationApi.get(), listSkills()])
    rows.value = navigationRows(config.nodes)
    revision.value = config.revision
    skills.value = response.data || []
    saved.value = JSON.stringify(rows.value)
    selectedId.value = rows.value[0]?.id || ''
    ready.value = true
  } catch {
    error.value = '配置或技能列表加载失败，请重新加载'
  } finally {
    loading.value = false
  }
}
const reload = () => {
  if (dirty.value) Modal.confirm({ title: '放弃未保存修改并重新加载？', onOk: load })
  else load()
}
const add = () => {
  const id = createNavigationEntryId()
  rows.value.push({
    id,
    parentId: '',
    label: '',
    skillSlug: '',
    skillDisplayName: '',
    inputHint: '',
    outputHint: '',
    presetPrompt: ''
  })
  selectedId.value = id
}
const bindSkill = (slug) => {
  selected.value.skillSlug = slug
  selected.value.skillDisplayName = getSkillDisplayName(
    slug,
    skills.value.find((s) => s.slug === slug)?.name || slug
  )
}
const remove = () => {
  const id = selectedId.value
  const removed = new Set([id, ...descendantIds(rows.value, id)])
  Modal.confirm({
    title: `删除此入口及其 ${removed.size - 1} 个子入口？`,
    content: '技能本体和历史对话不会删除，保存配置后生效。',
    okText: '删除入口',
    okType: 'danger',
    onOk: () => {
      rows.value = rows.value.filter((row) => !removed.has(row.id))
      selectedId.value = rows.value[0]?.id || ''
    }
  })
}
const save = async () => {
  saving.value = true
  error.value = ''
  try {
    for (const row of rows.value) {
      if (
        ['label', 'skillSlug', 'skillDisplayName', 'inputHint', 'outputHint', 'presetPrompt'].some(
          (key) => !row[key]?.trim()
        )
      ) {
        selectedId.value = row.id
        throw new Error('请填写入口名称、绑定技能、中文显示名、材料、用途和提示词')
      }
    }
    const config = await skillNavigationApi.save({
      revision: revision.value,
      nodes: navigationTree(rows.value)
    })
    store.accept(config)
    revision.value = config.revision
    rows.value = navigationRows(config.nodes)
    saved.value = JSON.stringify(rows.value)
    message.success('已保存，侧栏及项目技能菜单已更新')
  } catch (err) {
    error.value = err.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<style scoped>
h2 {
  margin: 0 0 12px;
}
.hint {
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.warning {
  color: var(--color-warning, #ad6800);
  font-size: 12px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 16px 0;
}
.editor {
  display: grid;
  grid-template-columns: minmax(140px, 2fr) minmax(0, 3fr);
  gap: 20px;
}
.entry-list {
  border-right: 1px solid var(--gray-150);
  padding-right: 8px;
}
.entry-row {
  display: flex;
  align-items: center;
  border-radius: 6px;
}
.entry-row.selected {
  background: var(--main-10);
}
.entry-row button {
  background: transparent;
  border: 0;
  color: var(--color-text);
  padding: 8px 5px;
  cursor: pointer;
}
.entry-row button:disabled {
  opacity: 0.3;
  cursor: default;
}
.entry-select {
  flex: 1;
  text-align: left;
  min-width: 0;
  overflow-wrap: anywhere;
}
@media (max-width: 700px) {
  .editor {
    grid-template-columns: 1fr;
  }
  .entry-list {
    max-height: 200px;
    overflow: auto;
    border-right: 0;
  }
}
</style>
