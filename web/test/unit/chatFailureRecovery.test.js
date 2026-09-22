import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, computed } from 'vue'

const chat = readFileSync(
  new URL('../../src/components/AgentChatComponent.vue', import.meta.url),
  'utf8'
)
const upload = readFileSync(
  new URL('../../src/components/AttachmentTmpUploadModal.vue', import.meta.url),
  'utf8'
)
const base = readFileSync(new URL('../../src/apis/base.js', import.meta.url), 'utf8')

function callback(source, name, env) {
  const match = source.match(new RegExp('const ' + name + ' = [\\s\\S]*?\\n}', 'm'))
  assert.ok(match, name)
  return new Function(...Object.keys(env), match[0] + '; return ' + name)(...Object.values(env))
}

test('发送状态已存在时只恢复历史；不存在时重发原编号和原 payload', async () => {
  for (const exists of [true, false]) {
    const payload = {
      query: '保留正文',
      meta: { request_id: 'original' },
      model_spec: 'original-model'
    }
    const failedSends = ref({ t: { payload, busy: false } })
    const sent = []
    const selected = []
    const retry = callback(chat, 'retryFailedSend', {
      currentChatId: ref('t'),
      failedSends,
      agentApi: {
        getRequest: async (id) => {
          assert.equal(id, 'original')
          if (!exists) throw { status: 404 }
          return { request: { status: 'running' } }
        },
        createAgentRun: async (value) => {
          sent.push(value)
          return { status: 'queued' }
        }
      },
      selectChat: async (id) => selected.push(id)
    })
    await retry()
    assert.equal(sent.length, exists ? 0 : 1)
    if (!exists) assert.deepEqual(sent[0], payload)
    assert.deepEqual(selected, ['t'])
    assert.equal(failedSends.value.t, undefined)
  }
})

test('核对失败不盲目重发', async () => {
  const currentChatId = ref('a')
  const failedSends = ref({ a: { payload: { meta: { request_id: 'r' } }, busy: false } })
  let posts = 0
  const retry = callback(chat, 'retryFailedSend', {
    currentChatId,
    failedSends,
    agentApi: {
      getRequest: async () => {
        throw new Error('offline')
      },
      createAgentRun: async () => posts++
    },
    selectChat: async () => assert.fail('cannot change thread')
  })
  await retry()
  assert.equal(posts, 0)
  assert.match(failedSends.value.a.error, /检查网络/)
  assert.equal(failedSends.value.a.busy, false)
})

test('恢复明确拒绝的发送内容时保留后续草稿；未知状态不能编辑重发', () => {
  const userInput = ref('后续草稿')
  const failedSends = ref({ t: { payload: { query: '原问题' }, rejected: false } })
  const edit = callback(chat, 'editFailedSend', {
    currentChatId: ref('t'),
    failedSends,
    userInput,
    agentInputAreaRef: ref(null)
  })
  edit()
  assert.equal(userInput.value, '后续草稿')
  failedSends.value.t.rejected = true
  edit()
  assert.equal(userInput.value, ['原问题', '后续草稿'].join(String.fromCharCode(10)))
  assert.equal(failedSends.value.t, undefined)
})

test('附件 GET 失败保留上次内容、提供错误状态；重试成功清除错误', async () => {
  const cached = [{ file_id: 'f', name: 'report.docx' }]
  const threadAttachmentsMap = ref({ t: cached })
  const attachmentLoadErrors = ref({})
  const attachmentLoading = ref({})
  let fail = true
  const refresh = callback(chat, 'fetchThreadAttachments', {
    threadAttachmentsMap,
    attachmentLoadErrors,
    attachmentLoading,
    attachmentLoadVersions: new Map(),
    threadApi: {
      getThreadAttachments: async () => {
        if (fail) throw Error()
        return { attachments: [] }
      }
    }
  })
  await refresh('t')
  assert.deepEqual(threadAttachmentsMap.value.t, cached)
  assert.ok(attachmentLoadErrors.value.t)
  assert.equal(attachmentLoading.value.t, false)
  fail = false
  await refresh('t')
  assert.deepEqual(threadAttachmentsMap.value.t, [])
  assert.equal(attachmentLoadErrors.value.t, undefined)
})

test('旧附件响应不能覆盖新刷新结果', async () => {
  const resolvers = []
  const env = {
    threadAttachmentsMap: ref({}),
    attachmentLoadErrors: ref({}),
    attachmentLoading: ref({}),
    attachmentLoadVersions: new Map(),
    threadApi: { getThreadAttachments: () => new Promise((resolve) => resolvers.push(resolve)) }
  }
  const refresh = callback(chat, 'fetchThreadAttachments', env)
  const first = refresh('t')
  const second = refresh('t')
  resolvers[1]({ attachments: [{ file_id: 'new' }] })
  await second
  resolvers[0]({ attachments: [] })
  await first
  assert.equal(env.threadAttachmentsMap.value.t[0].file_id, 'new')
})

test('批量部分成功仅移除已确认项，失败项保留且弹窗不关闭', async () => {
  const fileItems = ref([
    { localId: 1, status: 'uploaded', objectName: 'ok' },
    { localId: 2, status: 'error' }
  ])
  const events = []
  const env = {
    fileItems,
    confirming: ref(false),
    confirmDisabled: ref(false),
    confirmableItems: computed(() => fileItems.value.filter((x) => x.status === 'uploaded')),
    props: { threadId: 't' },
    threadApi: {
      confirmTmpThreadAttachments: async (id, items) => {
        assert.equal(id, 't')
        assert.equal(items.length, 1)
        return {}
      }
    },
    message: { success() {}, error: assert.fail },
    getErrorMessage: (e) => e.message,
    emit: (...args) => events.push(args)
  }
  await callback(upload, 'handleConfirm', env)()
  assert.deepEqual(
    fileItems.value.map((x) => x.localId),
    [2]
  )
  assert.deepEqual(
    events.map((x) => x[0]),
    ['added']
  )
  assert.equal(env.confirming.value, false)
})

test('添加关联失败保留全部上传项，允许再次确认', async () => {
  const items = [{ localId: 1, status: 'uploaded' }]
  const env = {
    fileItems: ref(items),
    confirming: ref(false),
    confirmDisabled: ref(false),
    confirmableItems: ref(items),
    props: { threadId: 't' },
    threadApi: {
      confirmTmpThreadAttachments: async () => {
        throw Error('offline')
      }
    },
    message: { success: assert.fail, error() {} },
    getErrorMessage: (e) => e.message,
    emit: assert.fail
  }
  await callback(upload, 'handleConfirm', env)()
  assert.equal(env.fileItems.value.length, 1)
})

test('业务提示只接受技能路径白名单，未知异常不展示内部信息', () => {
  const source = base.slice(
    base.indexOf('const SKILL_ERROR_MESSAGES'),
    base.indexOf('export async function apiRequest')
  )
  const publicMessage = new Function('safeRequestMetadata', source + ';return publicErrorMessage')(
    (url) => ({ path: url })
  )
  const headers = new Headers()
  assert.doesNotThrow(() =>
    publicMessage('/api/skills/upload', 400, headers, true, {
      detail: { code: { toString: null } }
    })
  )
  assert.match(
    publicMessage('/api/skills/upload', 400, headers, true, {
      detail: { code: 'skill_manifest_missing' }
    }),
    /缺少 SKILL.md/
  )
  assert.doesNotMatch(
    publicMessage('/api/auth/token', 400, headers, false, {
      detail: { code: 'skill_manifest_missing' }
    }),
    /SKILL/
  )
  assert.doesNotMatch(
    publicMessage('/api/skills/upload', 400, headers, true, { detail: '/secret/token' }),
    /secret|token/
  )
  assert.doesNotMatch(publicMessage('/api/skills/upload', 500, headers, true, {}), /docker|logs/)
})

test('HTTP 200 的业务拒绝仍保留失败内容供重新编辑', async () => {
  const failedSends = ref({
    t: { payload: { meta: { request_id: 'r' }, query: '原消息' }, busy: false }
  })
  const retry = callback(chat, 'retryFailedSend', {
    currentChatId: ref('t'),
    failedSends,
    agentApi: {
      getRequest: async () => ({ request: { status: 'rejected' } }),
      createAgentRun: assert.fail
    },
    selectChat: assert.fail
  })
  await retry()
  assert.equal(failedSends.value.t.rejected, true)
  assert.equal(failedSends.value.t.payload.query, '原消息')
})

test('重试途中切换线程，不跳回原对话', async () => {
  const currentChatId = ref('a')
  const failedSends = ref({ a: { payload: { meta: { request_id: 'r' } }, busy: false } })
  const retry = callback(chat, 'retryFailedSend', {
    currentChatId,
    failedSends,
    agentApi: {
      getRequest: async () => {
        currentChatId.value = 'b'
        return { request: { status: 'completed' } }
      }
    },
    selectChat: assert.fail
  })
  await retry()
  assert.equal(currentChatId.value, 'b')
  assert.equal(failedSends.value.a, undefined)
})

test('删除失败恢复附件；删除成功但刷新失败保留服务器确认的删除结果', async () => {
  for (const deleteFails of [true, false]) {
    const threadAttachmentsMap = ref({ t: [{ file_id: 'f' }] })
    const errors = []
    const remove = callback(chat, 'handleAttachmentRemove', {
      currentChatId: ref('t'),
      currentAgentId: ref('a'),
      threadAttachmentsMap,
      threadApi: {
        deleteThreadAttachment: async () => {
          if (deleteFails) throw Error('offline')
        }
      },
      fetchAgentState: async () => {},
      fetchThreadAttachments: async () => {
        errors.push('refresh failure')
      },
      handleChatError: () => errors.push('delete failure')
    })
    await remove({ file_id: 'f' })
    assert.equal(threadAttachmentsMap.value.t.length, deleteFails ? 1 : 0)
    assert.deepEqual(errors, [deleteFails ? 'delete failure' : 'refresh failure'])
  }
})
