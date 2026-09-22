import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { compileScript, parse } from 'vue/compiler-sfc'

const { descriptor } = parse(
  readFileSync(new URL('../../src/components/FormalDocumentCenter.vue', import.meta.url), 'utf8')
)
const { scriptSetupAst } = compileScript(descriptor, { id: 'document-upload-test' })
const code = scriptSetupAst
  .filter(
    (n) =>
      n.type === 'FunctionDeclaration' && ['upload', 'perform', 'applyDetail'].includes(n.id.name)
  )
  .map((n) => descriptor.scriptSetup.content.slice(n.start, n.end))
  .join('\n')

function setup(upload) {
  const context = vm.createContext({
    document: { value: { id: 'doc', revision: 1 } },
    selected: { value: ['current'] },
    comment: { value: '保留办理意见' },
    confirmed: { value: true },
    busy: { value: false },
    error: { value: '' },
    uploading: { value: false },
    progress: { value: 0 },
    controller: null,
    AbortController,
    formalDocumentApi: { upload },
    message: { success() {}, warning() {} },
    event: { target: { value: 'file', files: [{ size: 100 }] } }
  })
  vm.runInContext(code, context)
  return { context, run: () => vm.runInContext('upload(event)', context) }
}

test('上传保留当前勾选与意见，不恢复已取消的历史旧版，并要求重新确认', async () => {
  const state = setup(async () => ({
    id: 'doc',
    revision: 2,
    files: [{ id: 'old' }, { id: 'current' }, { id: 'new' }],
    events: [{ detail: { file_ids: ['old'] } }]
  }))
  await state.run()
  assert.deepEqual(Array.from(state.context.selected.value), ['current', 'new'])
  assert.equal(state.context.comment.value, '保留办理意见')
  assert.equal(state.context.confirmed.value, false)
  assert.equal(state.context.document.value.revision, 2)
})

test('连续上传两份草稿文件均保持勾选', async () => {
  let sequence = 0
  const files = []
  const state = setup(async () => {
    files.push({ id: `file-${++sequence}` })
    return { id: 'doc', revision: sequence, files: [...files], events: [] }
  })
  state.context.selected.value = []
  await state.run()
  await state.run()
  assert.deepEqual(Array.from(state.context.selected.value), ['file-1', 'file-2'])
})

test('上传失败保留清单和办理意见，解除繁忙状态', async () => {
  const state = setup(async () => {
    throw new Error('上传失败')
  })
  await state.run()
  assert.deepEqual(Array.from(state.context.selected.value), ['current'])
  assert.equal(state.context.comment.value, '保留办理意见')
  assert.equal(state.context.document.value.revision, 1)
  assert.equal(state.context.confirmed.value, true)
  assert.equal(state.context.error.value, '上传失败')
  assert.equal(state.context.busy.value, false)
  assert.equal(state.context.uploading.value, false)
})
