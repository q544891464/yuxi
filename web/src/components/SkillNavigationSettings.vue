<template>
  <section class="navigation-settings">
    <h2>侧栏技能</h2>
    <p class="hint">
      为登录用户整理共享技能菜单。删除菜单入口不会删除技能本体，也不会改变技能权限。
    </p>
    <p v-if="!configured" class="hint">未配置时显示全部可访问技能；保存空菜单会隐藏共享菜单。</p>
    <a-alert v-if="error" type="error" :message="error" show-icon />
    <a-alert
      v-if="refreshError"
      type="warning"
      message="配置已保存，但侧栏刷新失败。可以重试刷新，或重新加载页面。"
      show-icon
    >
      <template #action><a-button size="small" @click="refreshMenu">重试刷新</a-button></template>
    </a-alert>
    <a-spin :spinning="loading">
      <div class="toolbar">
        <a-button :disabled="loading || saving" @click="reload">重新加载</a-button>
        <a-button :disabled="!ready || saving || loading" @click="addNode('group')"
          >添加分组</a-button
        >
        <a-button :disabled="!ready || saving || loading" @click="addNode('entry')"
          >添加技能入口</a-button
        >
        <a-button
          type="primary"
          :loading="saving"
          :disabled="!ready || loading || !dirty"
          @click="save"
        >
          保存配置
        </a-button>
        <span v-if="dirty" class="hint">有未保存修改</span>
      </div>
      <div v-if="ready" class="editor">
        <div class="entry-list">
          <p v-if="!rows.length" class="hint">
            暂无入口。可添加分组或技能入口；空树会隐藏共享技能菜单。
          </p>
          <div
            v-for="row in orderedRows"
            :key="row.id"
            class="entry-row"
            :class="{ selected: selectedId === row.id }"
          >
            <button
              type="button"
              class="entry-select"
              :style="{ paddingLeft: `${8 + row.depth * 12}px` }"
              @click="selectedId = row.id"
            >
              <span class="kind-label">{{ isGroup(row) ? '分组' : '技能' }}</span>
              {{ row.name || '未命名' }}
            </button>
            <button
              type="button"
              :aria-label="`上移${row.name}`"
              :disabled="!canMove(row, -1) || saving"
              @click="moveNavigationRow(rows, row.id, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              :aria-label="`下移${row.name}`"
              :disabled="!canMove(row, 1) || saving"
              @click="moveNavigationRow(rows, row.id, 1)"
            >
              ↓
            </button>
          </div>
        </div>
        <a-form v-if="selected" layout="vertical" class="entry-form" :disabled="saving">
          <a-form-item :label="isGroup(selected) ? '分组名称' : '技能中文显示名'" required>
            <a-input v-model:value="selected.name" :maxlength="60" />
          </a-form-item>
          <a-form-item label="父级分组">
            <a-select v-model:value="selected.parentId" :options="parentOptions" />
          </a-form-item>
          <a-form-item label="可见角色">
            <a-select
              v-model:value="selected.visibleRoles"
              mode="multiple"
              :options="roleOptions"
            />
            <p class="hint">
              未选择角色时隐藏该节点；隐藏分组也会隐藏其下级。此设置不改变技能访问权限。
            </p>
          </a-form-item>
          <template v-if="!isGroup(selected)">
            <a-form-item label="绑定可访问的已启用共享技能" required>
              <a-select
                :value="selected.skillSlug"
                :options="skillOptions"
                show-search
                option-filter-prop="label"
                @change="bindSkill"
              />
              <p
                v-if="!skillOptions.some((skill) => skill.value === selected.skillSlug)"
                class="warning"
              >
                当前绑定不在可选技能中。新绑定请选择已启用的共享技能。
              </p>
            </a-form-item>
            <a-form-item label="准备材料（可选）">
              <a-textarea v-model:value="selected.material" :rows="2" :maxlength="2000" />
            </a-form-item>
            <a-form-item label="功能用途与结果（可选）">
              <a-textarea v-model:value="selected.result" :rows="2" :maxlength="2000" />
            </a-form-item>
            <a-form-item label="预设提示词（可选）">
              <a-textarea v-model:value="selected.prompt" :rows="4" :maxlength="10000" />
              <p class="hint">技能引用由系统自动添加，此处填写任务指令。</p>
            </a-form-item>
          </template>
          <a-button danger @click="remove"
            >删除此{{ isGroup(selected) ? '分组' : '入口' }}及其子项</a-button
          >
        </a-form>
      </div>
    </a-spin>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { listAccessibleSkills } from '@/apis/skill_api'
import { skillNavigationApi } from '@/apis/skill_navigation_api'
import { useSkillNavigationStore } from '@/stores/skillNavigation'
import {
  createNavigationEntryId,
  descendantIds,
  moveNavigationRow,
  navigationRows,
  navigationTree
} from '@/utils/skillNavigationEditor'

const roleOptions = [
  { value: 'user', label: '普通用户' },
  { value: 'admin', label: '管理员' },
  { value: 'superadmin', label: '超级管理员' }
]
const store = useSkillNavigationStore()
const rows = ref([])
const skills = ref([])
const selectedId = ref('')
const revision = ref(0)
const configured = ref(false)
const saved = ref('[]')
const ready = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const refreshError = ref(false)
const dirty = computed(() => JSON.stringify(rows.value) !== saved.value || !configured.value)
const selected = computed(() => rows.value.find((row) => row.id === selectedId.value))
const isGroup = (row) => row.kind === 'group'
const orderedRows = computed(() => {
  const visit = (parentId, depth) =>
    rows.value
      .filter((row) => row.parentId === parentId)
      .flatMap((row) => [{ ...row, depth }, ...visit(row.id, depth + 1)])
  return visit('', 0)
})
const skillOptions = computed(() =>
  skills.value
    .filter(
      (skill) =>
        skill.enabled !== false &&
        skill.sourceScope !== 'personal' &&
        skill.source_scope !== 'personal'
    )
    .map((skill) => ({
      value: skill.slug,
      label: `${skill.name || skill.slug}（${skill.slug}）`
    }))
)
const subtreeHeight = (id) =>
  Math.max(
    0,
    ...rows.value.filter((row) => row.parentId === id).map((row) => 1 + subtreeHeight(row.id))
  )
const parentOptions = computed(() => {
  const moving = selected.value
  const excluded = new Set(moving ? [moving.id, ...descendantIds(rows.value, moving.id)] : [])
  const movedHeight = moving ? subtreeHeight(moving.id) : 0
  return [
    { value: '', label: '顶级' },
    ...orderedRows.value
      .filter((row) => !excluded.has(row.id) && isGroup(row) && row.depth + 1 + movedHeight < 3)
      .map((row) => ({
        value: row.id,
        label: `${'　'.repeat(row.depth + 1)}${row.name || '未命名分组'}`
      }))
  ]
})
const canMove = (row, direction) => {
  const siblings = rows.value.filter((item) => item.parentId === row.parentId)
  return !!siblings[siblings.findIndex((item) => item.id === row.id) + direction]
}
const load = async () => {
  loading.value = true
  error.value = ''
  refreshError.value = false
  try {
    const [config, response] = await Promise.all([
      skillNavigationApi.manage(),
      listAccessibleSkills()
    ])
    rows.value = navigationRows(config.tree || [])
    revision.value = config.revision
    configured.value = config.configured
    skills.value = response?.data || []
    saved.value = JSON.stringify(rows.value)
    selectedId.value = rows.value[0]?.id || ''
    ready.value = true
  } catch {
    error.value = '配置或技能列表加载失败，请重新加载。'
  } finally {
    loading.value = false
  }
}
const reload = () => {
  if (dirty.value) Modal.confirm({ title: '放弃未保存修改并重新加载？', onOk: load })
  else load()
}
const addNode = (kind) => {
  const parentRow = selected.value && isGroup(selected.value) ? selected.value : null
  const parentDepth = orderedRows.value.find((row) => row.id === parentRow?.id)?.depth
  const parentId = parentRow && parentDepth < 2 ? parentRow.id : selected.value?.parentId || ''
  const id = createNavigationEntryId()
  rows.value.push({
    id,
    parentId,
    name: '',
    kind,
    skillSlug: '',
    material: '',
    result: '',
    prompt: '',
    visibleRoles: roleOptions.map((role) => role.value)
  })
  selectedId.value = id
}
const bindSkill = (slug) => {
  selected.value.skillSlug = slug
  if (!selected.value.name?.trim()) {
    selected.value.name = skills.value.find((skill) => skill.slug === slug)?.name || ''
  }
}
const remove = () => {
  const id = selectedId.value
  const removed = new Set([id, ...descendantIds(rows.value, id)])
  Modal.confirm({
    title: `删除此节点及其 ${removed.size - 1} 个子节点？`,
    content: '这只会移除侧栏入口，不会删除技能或历史数据。',
    okText: '删除入口',
    okType: 'danger',
    onOk: () => {
      rows.value = rows.value.filter((row) => !removed.has(row.id))
      selectedId.value = rows.value[0]?.id || ''
    }
  })
}
const refreshMenu = async () => {
  refreshError.value = false
  try {
    store.invalidate()
    await store.load({ force: true })
  } catch {
    refreshError.value = true
  }
}
const save = async () => {
  saving.value = true
  error.value = ''
  refreshError.value = false
  try {
    for (const row of rows.value) {
      if (!row.name?.trim()) {
        selectedId.value = row.id
        throw new Error('请填写所有分组和技能入口的名称。')
      }
      if (!isGroup(row) && !row.skillSlug?.trim()) {
        selectedId.value = row.id
        throw new Error('请绑定一个可访问且已启用的共享技能。')
      }
    }
    const config = await skillNavigationApi.save({
      revision: revision.value,
      tree: navigationTree(rows.value)
    })
    revision.value = config.revision
    configured.value = config.configured
    rows.value = navigationRows(config.tree || [])
    saved.value = JSON.stringify(rows.value)
    selectedId.value =
      rows.value.find((row) => row.id === selectedId.value)?.id || rows.value[0]?.id || ''
    message.success('侧栏技能配置已保存。')
    await refreshMenu()
  } catch (err) {
    error.value =
      err?.status === 409
        ? '配置版本已被其他管理员更新。请重新加载最新配置后再保存。'
        : err?.message || '保存失败，请修改后重试。'
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
  grid-template-columns: minmax(150px, 2fr) minmax(0, 3fr);
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
  min-width: 0;
  text-align: left;
  overflow-wrap: anywhere;
}
.kind-label {
  margin-right: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
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
