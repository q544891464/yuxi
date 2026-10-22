import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, ref } from 'vue'
import { useStarterTaskDraft } from '../../src/composables/useStarterTaskDraft.js'
import { createThreadDraftStore, createThreadDraftSession } from '../../src/utils/thread_draft.js'

test('示例需预览确认，保留原稿不改输入；确认后仍为可编辑草稿', () => {
  const scope = effectScope()
  scope.run(() => {
    const userInput = ref('已有任务')
    const draft = useStarterTaskDraft({
      contextKey: ref('user:a:project'),
      examples: ref([{ id: 'one', prompt: '示例正文' }]),
      enabled: ref(true),
      userInput
    })
    assert.equal(draft.open('unknown'), false)
    assert.equal(draft.open('one'), true)
    assert.equal(userInput.value, '已有任务')
    assert.equal(draft.hasDraft.value, true)
    draft.dismiss()
    assert.equal(draft.apply(), false)
    assert.equal(userInput.value, '已有任务')
    draft.open('one')
    assert.equal(draft.apply(), true)
    assert.equal(userInput.value, '示例正文')
    userInput.value += '\n补充材料'
    assert.equal(userInput.value, '示例正文\n补充材料')
  })
  scope.stop()
})

test('切换员工、项目、账号或会话、配置不可用及输入变化均使旧预览失效', () => {
  const scope = effectScope()
  scope.run(() => {
    const contextKey = ref('user:a:project')
    const examples = ref([{ id: 'one', prompt: 'A 示例' }])
    const enabled = ref(true)
    const userInput = ref('原稿')
    const draft = useStarterTaskDraft({ contextKey, examples, enabled, userInput })
    for (const key of [
      'user:b:project',
      'user:b:other-project',
      'other-user:b:project',
      'user:b:thread'
    ]) {
      draft.open('one')
      contextKey.value = key
      assert.equal(draft.preview.value, null)
      assert.equal(draft.apply(), false)
      assert.equal(userInput.value, '原稿')
    }
    draft.open('one')
    enabled.value = false
    assert.equal(draft.apply(), false)
    assert.equal(draft.open('one'), false)
    enabled.value = true
    draft.open('one')
    userInput.value = '新编辑内容'
    assert.equal(draft.apply(), false)
    assert.equal(userInput.value, '新编辑内容')
    draft.open('one')
    examples.value = []
    assert.equal(draft.apply(), false)
  })
  scope.stop()
})

test('示例写入后按员工保存，快速切换与刷新不会把 A 草稿交给 B', () => {
  const data = new Map()
  const store = createThreadDraftStore({
    getItem: (key) => data.get(key),
    setItem: (key, value) => data.set(key, value),
    removeItem: (key) => data.delete(key)
  })
  const session = createThreadDraftSession(store, '', 'user:a:project')
  session.saveInput('A 的示例与补充材料')
  assert.equal(session.switchDraftContext('user:b:project', 'A 的示例与补充材料'), '')
  session.saveInput('B 的任务')
  assert.equal(session.switchDraftContext('user:a:project', 'B 的任务'), 'A 的示例与补充材料')
  assert.equal(store.read('user:b:project'), 'B 的任务')
})
