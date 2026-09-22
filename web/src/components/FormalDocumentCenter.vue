<script setup>
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { documentRequestId } from '@/utils/documentRequestId'
import { formalDocumentApi } from '@/apis/formal_document_api'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['update:open'])
const category = ref('pending')
const search = ref('')
const items = ref([])
const hasMore = ref(false)
const document = ref(null)
const workflows = ref([])
const creating = ref(false)
const draft = ref({})
const busy = ref(false)
const error = ref('')
const selected = ref([])
const confirmed = ref(false)
const comment = ref('')
const progress = ref(0)
const uploading = ref(false)
const uploadInput = ref(null)
const statusNames = {
  draft: '草稿',
  in_progress: '办理中',
  returned: '退回补正',
  archived: '已归档'
}
const actionNames = {
  create: '建立文书',
  upload: '上传版本',
  submit: '确认移交',
  return: '退回补正',
  archive: '确认归档'
}
let controller
watch(selected, () => {
  confirmed.value = false
})
async function perform(work) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function load(more = false) {
  const result = await formalDocumentApi.list({
    category: category.value,
    search: search.value,
    offset: more ? items.value.length : 0
  })
  items.value = more ? [...items.value, ...result.items] : result.items
  hasMore.value = result.has_more
}
function applyDetail(value) {
  document.value = value
  // 保留最新一次正式提交的选择，避免自动把旧版全部再次提交。
  const submission = [...value.events].reverse().find((e) => e.detail.file_ids)
  selected.value = submission?.detail.file_ids || []
  confirmed.value = false
  comment.value = ''
}
function openDocument(id) {
  return perform(async () => {
    applyDetail(await formalDocumentApi.detail(id))
    creating.value = false
  })
}
function newDocument() {
  document.value = null
  creating.value = true
  draft.value = { request_id: documentRequestId(), title: '', case_number: '', workflow_id: null }
}
function create() {
  return perform(async () => {
    applyDetail(await formalDocumentApi.create(draft.value))
    creating.value = false
    await load()
  })
}
async function upload(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.size || file.size > 10 * 1024 * 1024) {
    message.warning('请选择非空且不超过10MB的文件')
    return
  }
  await perform(async () => {
    controller = new AbortController()
    uploading.value = true
    progress.value = 0
    try {
      const result = await formalDocumentApi.upload(
        document.value.id,
        document.value.revision,
        file,
        {
          signal: controller.signal,
          onUploadProgress: (p) => {
            progress.value = p
          }
        }
      )
      // 上传只刷新文件版本，不能用历史提交清单覆盖用户正在编辑的选择和意见。
      document.value = result
      confirmed.value = false
      selected.value = [...new Set([...selected.value, result.files.at(-1).id])]
      message.success('已保存新版本，请勾选正式文件后确认提交')
    } finally {
      uploading.value = false
      controller = null
    }
  })
}
function act(action) {
  return perform(async () => {
    applyDetail(
      await formalDocumentApi.act(document.value.id, {
        revision: document.value.revision,
        action,
        confirmed: confirmed.value,
        comment: comment.value,
        file_ids: selected.value
      })
    )
    message.success(action === 'return' ? '已退回补正' : '已确认提交')
    await load()
  })
}
function download(file) {
  return perform(async () => {
    const blob = await formalDocumentApi.download(document.value.id, file.id)
    const url = URL.createObjectURL(blob)
    const anchor = window.document.createElement('a')
    anchor.href = url
    anchor.download = file.filename
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
}
watch(
  () => props.open,
  (open) => {
    if (open)
      void perform(async () => {
        workflows.value = (await formalDocumentApi.workflows()).workflows
        await load()
      })
  }
)
</script>

<template>
  <a-drawer
    :open="open"
    title="文书中心"
    width="min(1120px, 100vw)"
    :mask-closable="!busy"
    :closable="!busy"
    @close="emit('update:open', false)"
  >
    <a-alert v-if="error" type="error" :message="error" show-icon class="notice" />
    <div class="document-layout">
      <section class="document-list">
        <a-button type="primary" block :disabled="busy" @click="newDocument">上传正式文书</a-button>
        <a-select
          v-model:value="category"
          :disabled="busy"
          aria-label="文书分类"
          @change="perform(() => load())"
        >
          <a-select-option value="pending">待我办理</a-select-option
          ><a-select-option value="mine">我提交的</a-select-option>
          <a-select-option value="archived">已归档</a-select-option
          ><a-select-option value="all">全部可见</a-select-option>
        </a-select>
        <a-input-search
          v-model:value="search"
          placeholder="文书名称 / 案件编号"
          :disabled="busy"
          @search="perform(() => load())"
        />
        <a-button :disabled="busy" @click="perform(() => load())">刷新列表</a-button>
        <a-empty v-if="!items.length && !busy" description="暂无文书" />
        <button
          v-for="item in items"
          :key="item.id"
          class="document-item"
          :class="{ active: item.id === document?.id }"
          :disabled="busy"
          @click="openDocument(item.id)"
        >
          <strong>{{ item.title }}</strong
          ><span>{{ statusNames[item.status] }} · {{ item.step }}</span
          ><small>{{ item.case_number || '未填写案件编号' }}</small>
        </button>
        <a-button v-if="hasMore" :disabled="busy" @click="perform(() => load(true))"
          >加载更多</a-button
        >
      </section>
      <section class="document-detail" :aria-busy="busy">
        <a-form v-if="creating" layout="vertical" :model="draft">
          <h3>上传正式文书</h3>
          <p>先保存草稿，再上传并确认文件。草稿自动保留，可从“我提交的”继续办理。</p>
          <a-form-item label="文书名称" required
            ><a-input v-model:value="draft.title" :maxlength="200"
          /></a-form-item>
          <a-form-item label="案件编号"
            ><a-input v-model:value="draft.case_number" :maxlength="128"
          /></a-form-item>
          <a-form-item label="办理方式"
            ><a-select v-model:value="draft.workflow_id">
              <a-select-option :value="null">直接归档（仅本人和超级管理员可见）</a-select-option>
              <a-select-option v-for="flow in workflows" :key="flow.id" :value="flow.id"
                >{{ flow.name }} · {{ flow.steps.join(' → ') || '直接归档' }}</a-select-option
              >
            </a-select></a-form-item
          >
          <a-button type="primary" @click="create" :loading="busy" :disabled="!draft.title?.trim()"
            >创建草稿，下一步上传</a-button
          >
        </a-form>
        <template v-else-if="document">
          <div class="detail-heading">
            <h3>{{ document.title }}</h3>
            <a-button :disabled="busy" @click="openDocument(document.id)">刷新详情</a-button>
          </div>
          <p>
            {{ document.case_number }} · {{ document.workflow_name }} ·
            {{ statusNames[document.status] }} / {{ document.step }}
          </p>
          <h4>文件与版本</h4>
          <p v-if="document.assignee_names?.length">
            当前办理人：{{ document.assignee_names.join('、') }}
          </p>
          <p v-if="document.can_edit">
            勾选本次正式提交的文件。上传新版不会覆盖历史文件；请取消勾选被替代的旧版。
          </p>
          <a-empty v-if="!document.files.length" description="请上传待确认的正式文书" />
          <a-checkbox-group
            v-model:value="selected"
            class="formal-document-files"
            :disabled="busy || !document.can_edit"
          >
            <div v-for="file in document.files" :key="file.id" class="file-row">
              <a-checkbox :value="file.id" /><span class="file-meta"
                >V{{ file.sequence }} · {{ file.filename
                }}<small>{{ Math.ceil(file.size / 1024) }} KB</small></span
              >
              <a-button size="small" :disabled="busy" @click="download(file)">下载</a-button>
            </div>
          </a-checkbox-group>
          <template v-if="document.can_edit">
            <input
              ref="uploadInput"
              type="file"
              hidden
              accept=".pdf,.doc,.docx,.wps,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
              @change="upload"
            />
            <a-button :disabled="busy" @click="uploadInput.click()">上传文件 / 新版本</a-button>
            <small class="file-hint"
              >支持 PDF、Word/WPS、表格、文本和图片，单文件不超过10MB。</small
            >
            <div v-if="uploading">
              <a-progress :percent="progress" /><a-button @click="controller?.abort()"
                >取消上传</a-button
              >
            </div>
            <a-textarea
              v-model:value="comment"
              placeholder="办理意见（退回补正时必填）"
              :maxlength="2000"
              :rows="3"
              :disabled="busy"
            />
            <a-checkbox v-model:checked="confirmed" :disabled="busy"
              >我已核对勾选文件，确认作为本环节正式文书提交</a-checkbox
            >
            <a-space wrap>
              <a-button
                type="primary"
                :disabled="!confirmed || !selected.length || busy"
                @click="act('submit')"
                >{{
                  document.next_step === '归档' ? '确认归档' : `提交至${document.next_step}`
                }}</a-button
              >
              <a-button
                v-if="document.can_return"
                danger
                :disabled="!comment.trim() || busy"
                @click="act('return')"
                >退回补正</a-button
              >
            </a-space>
          </template>
          <a-alert
            v-else
            type="info"
            :message="
              document.status === 'archived'
                ? '已归档，文件和流转记录只读'
                : '当前由接收环节办理，您可查看历史文件和记录'
            "
          />
          <h4>流转记录</h4>
          <a-timeline
            ><a-timeline-item v-for="(event, index) in document.events" :key="index">
              <strong>{{ actionNames[event.action] }} · {{ event.actor }}</strong>
              <div>
                {{ event.detail.from_step
                }}{{ event.detail.to_step ? ` → ${event.detail.to_step}` : ''
                }}{{ event.detail.filename }}
              </div>
              <div v-if="event.detail.file_ids">
                确认文件：{{
                  document.files
                    .filter((f) => event.detail.file_ids.includes(f.id))
                    .map((f) => `V${f.sequence} ${f.filename}`)
                    .join('、')
                }}
              </div>
              <div>{{ event.detail.comment }}</div>
              <div v-if="event.detail.recipient_names?.length">
                接收人：{{ event.detail.recipient_names.join('、') }}
              </div>
              <small>{{ event.created_at }}</small>
            </a-timeline-item></a-timeline
          >
        </template>
        <a-empty v-else description="选择文书查看，或上传正式文书开始办理" />
      </section>
    </div>
  </a-drawer>
</template>

<style scoped>
.document-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 24px;
}
.document-list,
.document-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.document-list {
  align-self: start;
}
.document-item {
  text-align: left;
  background: var(--gray-0);
  color: var(--gray-900);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  display: grid;
  gap: 6px;
  overflow-wrap: anywhere;
}
.document-item.active {
  border-color: var(--main-color);
  background: var(--main-10);
}
.document-item span,
small,
p {
  color: var(--gray-600);
}
.detail-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
h3 {
  margin: 0;
  overflow-wrap: anywhere;
}
.formal-document-files {
  width: 100%;
  align-self: stretch;
  display: grid;
  gap: 8px;
}
.file-row {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--gray-150);
  padding: 8px 0;
}
.file-row > .file-meta {
  flex: 1;
  overflow-wrap: anywhere;
}
.file-row small {
  display: block;
}
.notice {
  margin-bottom: 16px;
}
@media (max-width: 700px) {
  .document-layout {
    grid-template-columns: 1fr;
  }
  .document-list {
    max-height: 280px;
    overflow: auto;
  }
}
</style>
