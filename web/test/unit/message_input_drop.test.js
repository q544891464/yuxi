import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { compileScript, parse } from 'vue/compiler-sfc'

const source = readFileSync(new URL('../../src/components/MessageInputComponent.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const { scriptSetupAst } = compileScript(descriptor, { id: 'input-drop-test' })
const handlers = ['hasTransferFiles', 'canAcceptUploadFiles', 'handleDragOver', 'handleDrop']
const code = scriptSetupAst
  .filter((node) => node.type === 'VariableDeclaration' && handlers.includes(node.declarations[0].id.name))
  .map((node) => descriptor.scriptSetup.content.slice(node.start, node.end))
  .join('\n')

for (const isLoading of [false, true]) {
  test(`文件拖拽在生成状态 ${isLoading} 时发出附件事件且阻止浏览器打开文件`, () => {
    const emitted = []
    const file = { name: '案件.wps' }
    const context = vm.createContext({
      props: { fileUploadEnabled: true, disabled: false, isLoading },
      isDraggingFiles: { value: false },
      emit: (...args) => emitted.push(args)
    })
    vm.runInContext(code, context)
    let prevented = 0
    const event = {
      dataTransfer: { types: ['Files'], files: [file] },
      preventDefault: () => prevented++,
      stopPropagation() {}
    }
    context.event = event
    vm.runInContext('handleDragOver(event); handleDrop(event)', context)
    assert.equal(prevented, 2)
    assert.equal(event.dataTransfer.dropEffect, 'copy')
    assert.equal(emitted.length, 1)
    assert.equal(emitted[0][0], 'drop-files')
    assert.equal(emitted[0][1][0], file)
    assert.equal(context.isDraggingFiles.value, false)
  })
}

test('禁用或不支持附件的输入框不发出上传事件', () => {
  for (const props of [
    { fileUploadEnabled: true, disabled: true },
    { fileUploadEnabled: false, disabled: false }
  ]) {
    const context = vm.createContext({
      props, isDraggingFiles: { value: false },
      emit: () => assert.fail('禁止上传时不能发出附件事件'),
      event: { dataTransfer: { types: ['Files'], files: [{}] }, preventDefault() {}, stopPropagation() {} }
    })
    vm.runInContext(code + '\nhandleDragOver(event); handleDrop(event)', context)
    assert.equal(context.event.dataTransfer.dropEffect, 'none')
  }
})
