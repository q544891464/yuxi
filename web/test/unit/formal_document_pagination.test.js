import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { compileScript, parse } from 'vue/compiler-sfc'

const { descriptor } = parse(
  readFileSync(new URL('../../src/components/FormalDocumentCenter.vue', import.meta.url), 'utf8')
)
const { scriptSetupAst } = compileScript(descriptor, { id: 'document-pagination-test' })
const node = scriptSetupAst.find((n) => n.type === 'FunctionDeclaration' && n.id.name === 'load')
const code = descriptor.scriptSetup.content.slice(node.start, node.end)

function setup() {
  const context = vm.createContext({
    category: { value: 'pending' },
    search: { value: '' },
    items: { value: [] },
    hasMore: { value: false },
    loadedQuery: { category: 'pending', search: '' },
    formalDocumentApi: {
      async list({ category, search, offset }) {
        if (search === '失败') throw new Error('搜索失败')
        return { items: [{ id: `${category}:${search}:${offset}` }], has_more: true }
      }
    }
  })
  vm.runInContext(code, context)
  return { context, load: (more = false) => vm.runInContext(`load(${more})`, context) }
}

test('未提交的新搜索文字不能改变当前列表的分页条件', async () => {
  const state = setup()
  await state.load()
  state.context.search.value = '另一案件'
  await state.load(true)
  assert.deepEqual(Array.from(state.context.items.value, (item) => item.id), [
    'pending::0',
    'pending::1'
  ])
})

test('新搜索成功替换列表后，分页沿用新查询', async () => {
  const state = setup()
  await state.load()
  state.context.search.value = '目标案件'
  state.context.category.value = 'archived'
  await state.load()
  state.context.search.value = '未提交'
  await state.load(true)
  assert.deepEqual(Array.from(state.context.items.value, (item) => item.id), [
    'archived:目标案件:0',
    'archived:目标案件:1'
  ])
})

test('新搜索失败后继续翻页仍使用已显示列表的查询', async () => {
  const state = setup()
  await state.load()
  state.context.search.value = '失败'
  state.context.category.value = 'archived'
  await assert.rejects(state.load(), /搜索失败/)
  await state.load(true)
  assert.deepEqual(Array.from(state.context.items.value, (item) => item.id), [
    'pending::0',
    'pending::1'
  ])
})
