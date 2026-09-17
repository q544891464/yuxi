import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { compileScript, parse } from 'vue/compiler-sfc'

const source = readFileSync(
  new URL('../../src/components/extensions/SkillCardList.vue', import.meta.url),
  'utf8'
)
const { descriptor } = parse(source)
const { scriptSetupAst } = compileScript(descriptor, { id: 'personal-export-test' })
const node = scriptSetupAst.find(
  (n) =>
    n.type === 'VariableDeclaration' && n.declarations[0].id.name === 'handleExportPersonalSkill'
)
const code = descriptor.scriptSetup.content.slice(node.start, node.end)

function setup(exporter, scope = 'personal') {
  const downloads = []
  const errors = []
  const revoked = []
  const context = vm.createContext({
    previewSkill: { value: { slug: 'my-skill', sourceScope: scope } },
    exportingPersonalSkill: { value: false },
    skillApi: { exportPersonalSkill: exporter },
    message: { error: (text) => errors.push(text) },
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL: (url) => revoked.push(url) },
    document: {
      createElement: () => ({
        click() {
          downloads.push({ href: this.href, name: this.download })
        }
      })
    }
  })
  vm.runInContext(code, context)
  return {
    context,
    downloads,
    errors,
    revoked,
    run: () => vm.runInContext('handleExportPersonalSkill()', context)
  }
}

test('个人技能导出锁定目标，避免重复请求，并释放下载 URL', async () => {
  let finish
  let calls = 0
  const state = setup((slug) => {
    assert.equal(slug, 'my-skill')
    calls++
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  const pending = state.run()
  assert.equal(state.context.exportingPersonalSkill.value, true)
  await state.run()
  state.context.previewSkill.value = { slug: 'another-skill', sourceScope: 'personal' }
  finish({ blob: async () => ({}) })
  await pending
  assert.equal(calls, 1)
  assert.deepEqual(state.downloads, [{ href: 'blob:test', name: 'my-skill.zip' }])
  assert.deepEqual(state.revoked, ['blob:test'])
  assert.equal(state.context.exportingPersonalSkill.value, false)
})

test('失败展示错误且恢复按钮，不下载错误响应', async () => {
  const state = setup(async () => {
    throw new Error('技能已删除')
  })
  await state.run()
  assert.deepEqual(state.errors, ['技能已删除'])
  assert.equal(state.downloads.length, 0)
  assert.equal(state.context.exportingPersonalSkill.value, false)
})

test('共享技能不能走个人导出接口', async () => {
  const state = setup(() => assert.fail('不应调用'), 'shared')
  await state.run()
  assert.equal(state.downloads.length, 0)
})

test('个人技能导入更新在确认页和结果列表显示更新语义', () => {
  const source = readFileSync(
    new URL('../../src/components/extensions/SkillInstallFlowModal.vue', import.meta.url),
    'utf8'
  )
  assert.match(source, /item\.personal_update/)
  assert.match(source, /确认安装\/更新/)
  assert.match(source, /item\.updated/)
  assert.match(source, /已更新/)
})
