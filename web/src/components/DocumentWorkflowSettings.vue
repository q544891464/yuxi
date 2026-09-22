<script setup>
import { onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { documentRequestId } from '@/utils/documentRequestId'
import { formalDocumentApi } from '@/apis/formal_document_api'
import DocumentScopeFields from './DocumentScopeFields.vue'

const config = ref({ revision: 0, workflows: [] })
const directory = ref({ users: [], departments: [] })
const busy = ref(false)
const error = ref('')
const scope = () => ({ user_uids: [], roles: [], department_ids: [] })
async function load() {
  busy.value = true
  try {
    const data = await formalDocumentApi.workflows(true)
    config.value = { revision: data.revision, workflows: data.workflows }
    directory.value = data.directory
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function add() {
  config.value.workflows.push({
    id: documentRequestId(),
    name: '',
    enabled: true,
    starters: scope(),
    steps: [],
    archive_readers: scope()
  })
}
function remove(index) {
  Modal.confirm({
    title: '删除此流程？',
    content: '仅影响新建文书，已提交文书保留原流程。',
    onOk: () => config.value.workflows.splice(index, 1)
  })
}
async function save() {
  busy.value = true
  try {
    const data = await formalDocumentApi.saveWorkflows(config.value)
    config.value = { revision: data.revision, workflows: data.workflows }
    message.success('流程已保存，新建文书使用新配置')
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="workflow-settings">
    <h2>文书流程</h2>
    <p>
      设置谁可发起、各环节由谁办理、归档后额外向谁开放。接收人可以上传新版、提交下一环节或退回补正。
    </p>
    <a-alert
      type="info"
      show-icon
      message="范围说明"
      description="指定人员与角色/部门筛选结果合并。角色和部门同时填写时须同时满足；全部留空代表无人。接收人在提交时确定，历史参与人保留查阅权限。流程修改仅影响新建文书。"
    />
    <a-alert v-if="error" type="error" :message="error" show-icon />
    <a-space
      ><a-button :disabled="busy" @click="add">添加流程</a-button
      ><a-button type="primary" :loading="busy" @click="save">保存配置</a-button
      ><a-button :disabled="busy" @click="load">重新加载</a-button></a-space
    >
    <a-empty
      v-if="!busy && !config.workflows.length"
      description="尚未配置流转流程，用户仍可直接归档个人文书"
    />
    <a-collapse v-if="config.workflows.length">
      <a-collapse-panel
        v-for="(workflow, index) in config.workflows"
        :key="workflow.id"
        :header="workflow.name || '新流程'"
      >
        <a-form layout="vertical">
          <a-form-item label="流程名称" required
            ><a-input v-model:value="workflow.name" :maxlength="80"
          /></a-form-item>
          <a-form-item label="启用"><a-switch v-model:checked="workflow.enabled" /></a-form-item>
          <a-form-item label="允许发起的人员范围" required
            ><DocumentScopeFields v-model="workflow.starters" :directory="directory"
          /></a-form-item>
          <div v-for="(step, stepIndex) in workflow.steps" :key="stepIndex" class="step-card">
            <a-form-item :label="`接收环节 ${stepIndex + 1}`" required
              ><a-input v-model:value="step.name" placeholder="例如：审理、督查" :maxlength="80"
            /></a-form-item>
            <DocumentScopeFields v-model="step.recipients" :directory="directory" />
            <a-space class="step-actions">
              <a-button
                size="small"
                :disabled="stepIndex === 0"
                @click="
                  workflow.steps.splice(stepIndex - 1, 0, workflow.steps.splice(stepIndex, 1)[0])
                "
                >上移</a-button
              >
              <a-button size="small" danger @click="workflow.steps.splice(stepIndex, 1)"
                >删除环节</a-button
              >
            </a-space>
          </div>
          <a-button @click="workflow.steps.push({ name: '', recipients: scope() })"
            >添加接收环节</a-button
          >
          <p>无接收环节时，确认后直接归档；有接收环节时，最后一环节确认后归档。</p>
          <a-form-item label="归档后额外可见范围（可留空）"
            ><DocumentScopeFields v-model="workflow.archive_readers" :directory="directory"
          /></a-form-item>
          <a-button danger @click="remove(index)">删除流程</a-button>
        </a-form>
      </a-collapse-panel>
    </a-collapse>
  </section>
</template>

<style scoped>
.workflow-settings {
  display: grid;
  gap: 16px;
}
.workflow-settings p {
  color: var(--gray-600);
  line-height: 1.6;
}
.step-card {
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
}
.step-actions {
  margin-top: 8px;
}
</style>
