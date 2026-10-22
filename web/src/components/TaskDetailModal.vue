<template>
  <a-modal :open="true" title="后台任务详情" :width="720" :footer="null" @cancel="$emit('close')">
    <div class="task-detail">
      <a-button :loading="loading" @click="loadTask">刷新任务记录</a-button>
      <a-alert v-if="error" type="error" show-icon :message="error" />
      <a-spin v-if="loading" />
      <template v-else-if="task">
        <h3>{{ task.name }}</h3>
        <p>
          执行状态：{{ TASK_STATUS_CONFIG[task.status]?.label || '未知' }}
          <span> · 更新于 {{ formatFullDateTime(task.updated_at) }}</span>
        </p>
        <a-alert v-if="task.error" type="error" show-icon :message="task.error" />
        <p v-if="task.message && !task.file_result_summary">{{ task.message }}</p>
        <section v-if="task.file_result_summary" aria-label="本次文件处理结果">
          <h4>本次文件处理结果</h4>
          <p class="file-result-summary">{{ formatFileResultSummary(task.file_result_summary) }}</p>
          <p class="task-detail-hint">以下是任务保存的处理记录，后续重试不会改写这些历史结果。</p>
          <a-alert
            v-if="task.file_result_summary.truncated"
            type="warning"
            show-icon
            :message="`结果记录已截断，仅保留 ${task.file_result_summary.recorded} 项明细；其余结果待核对。`"
          />
          <ul class="task-file-list">
            <li v-for="(item, index) in pageItems" :key="`${page}-${index}`">
              <strong>{{
                item.filename || item.original_filename || item.item || item.file_id || '未关联文件'
              }}</strong>
              <span>{{ fileResultStatusLabel(item.status) }}</span>
              <p v-if="item.error || item.error_message" class="task-file-error">
                {{ item.error || item.error_message }}
              </p>
              <a-button
                v-if="kbId && item.file_id"
                size="small"
                :loading="fileLoading && selectedFileId === item.file_id"
                @click="loadCurrentFile(item.file_id)"
                >查看当前文件状态</a-button
              >
              <span v-else class="task-detail-hint">缺少文件关联，可返回知识库核对。</span>
            </li>
          </ul>
          <a-pagination
            v-if="items.length > 10"
            v-model:current="page"
            :total="items.length"
            :page-size="10"
            :show-size-changer="false"
            size="small"
          />
        </section>
        <section v-if="selectedFileId" aria-label="文件当前状态" class="current-file-state">
          <h4>文件当前状态</h4>
          <a-spin v-if="fileLoading" />
          <a-alert v-else-if="fileError" type="warning" show-icon :message="fileError" />
          <template v-else-if="currentFile">
            <p>
              {{ currentFile.filename || selectedFileId }} ·
              {{ fileResultStatusLabel(currentFile.status) }}
            </p>
            <p>状态更新时间：{{ formatFullDateTime(currentFile.updated_at) }}</p>
            <p v-if="currentFile.error || currentFile.error_message" class="task-file-error">
              {{ currentFile.error || currentFile.error_message }}
            </p>
            <p class="task-detail-hint">
              当前状态可能包含本次任务之后的重试或其他操作，请与上方历史记录分别核对。
            </p>
          </template>
        </section>
        <a-button v-if="kbId" @click="openKnowledgeBase">返回知识库处理</a-button>
        <details>
          <summary>技术详情</summary>
          <pre>{{
            JSON.stringify(
              { id: task.id, message: task.message, payload: task.payload, result: task.result },
              null,
              2
            )
          }}</pre>
        </details>
      </template>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { taskerApi } from '@/apis/tasker'
import { documentApi } from '@/apis/knowledge_api'
import { useUserStore } from '@/stores/user'
import { formatFullDateTime } from '@/utils/time'
import {
  TASK_STATUS_CONFIG,
  fileResultStatusLabel,
  formatFileResultSummary
} from '@/utils/taskResults'

const props = defineProps({ taskId: { type: String, required: true } })
const emit = defineEmits(['close', 'open-knowledge'])
const router = useRouter()
const userStore = useUserStore()
const task = ref(null)
const loading = ref(false)
const error = ref('')
const page = ref(1)
const selectedFileId = ref(null)
const currentFile = ref(null)
const fileError = ref('')
const fileLoading = ref(false)
let taskRequest = 0
let fileRequest = 0
const kbId = computed(() => task.value?.payload?.kb_id || task.value?.result?.kb_id)
const items = computed(() =>
  Array.isArray(task.value?.result?.items) ? task.value.result.items : []
)
const pageItems = computed(() =>
  items.value.slice((page.value - 1) * 10, page.value * 10).map((item) => item || {})
)

/** 从任务详情接口读取持久结果，拒绝关闭、切换任务或账号后晚到的响应。 */
async function loadTask() {
  const request = ++taskRequest
  fileRequest += 1
  selectedFileId.value = null
  currentFile.value = null
  fileError.value = ''
  page.value = 1
  error.value = ''
  loading.value = true
  if (!userStore.isAdmin) {
    emit('close')
    return
  }
  try {
    const response = await taskerApi.fetchTaskDetail(props.taskId)
    if (request !== taskRequest) return
    if (!response?.task) throw new Error('任务记录不存在，请刷新任务列表。')
    task.value = response.task
  } catch (cause) {
    if (request === taskRequest) error.value = cause.message || '加载任务详情失败，请重试。'
  } finally {
    if (request === taskRequest) loading.value = false
  }
}

/** 按需核对一个关联文件，使用既有接口执行知识资源权限检查。 */
async function loadCurrentFile(fileId) {
  const request = ++fileRequest
  selectedFileId.value = fileId
  currentFile.value = null
  fileError.value = ''
  fileLoading.value = true
  try {
    const response = await documentApi.getDocumentBasicInfo(kbId.value, fileId)
    if (request !== fileRequest) return
    const metadata = response?.meta || response
    if (metadata?.file_id !== fileId) throw new Error('无法读取文件当前状态，请返回知识库核对。')
    currentFile.value = metadata
  } catch (cause) {
    if (request === fileRequest)
      fileError.value = cause.message || '文件不存在或无权访问，当前状态待核对。'
  } finally {
    if (request === fileRequest) fileLoading.value = false
  }
}

/** 返回当前知识库，在原有入口处理失败文件。 */
async function openKnowledgeBase() {
  await router.push({ name: 'ConsumerKnowledgeBaseDetail', params: { kbId: kbId.value } })
  emit('open-knowledge')
}

watch(
  [() => props.taskId, () => userStore.token, () => userStore.userRole],
  () => {
    task.value = null
    loadTask()
  },
  { immediate: true, flush: 'sync' }
)
onUnmounted(() => {
  taskRequest += 1
  fileRequest += 1
})
</script>

<style scoped lang="less">
.task-detail {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  overflow-wrap: anywhere;
  h3,
  h4,
  p {
    margin: 0;
  }
  h4 {
    margin-bottom: 8px;
  }
  section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  > .ant-btn {
    align-self: flex-start;
  }
  pre {
    max-height: 240px;
    overflow: auto;
    white-space: pre-wrap;
    font-size: 12px;
  }
  summary {
    cursor: pointer;
    color: var(--color-text-secondary);
  }
}
.task-detail-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.task-file-list {
  list-style: none;
  padding: 0;
  margin: 0;
  li {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding: 12px 0;
    border-bottom: 1px solid var(--gray-150);
  }
}
.task-file-error {
  color: var(--color-error-700);
}
.current-file-state {
  background: var(--gray-50);
  padding: 12px;
  border-radius: 8px;
}
</style>
