import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import { pathToFileURL, fileURLToPath } from 'node:url'
import test from 'node:test'
import { pid } from 'node:process'
import { compileScript, parse } from 'vue/compiler-sfc'
import { createRenderer, h } from 'vue'

function createHostNode(type) {
  return { type, props: {}, children: [], parent: null, text: '' }
}

const renderer = createRenderer({
  createElement: createHostNode,
  createText(text) {
    const node = createHostNode('text')
    node.text = text
    return node
  },
  createComment(text) {
    const node = createHostNode('comment')
    node.text = text
    return node
  },
  insert(child, parent, anchor = null) {
    child.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index >= 0) parent.children.splice(index, 0, child)
    else parent.children.push(child)
  },
  remove(child) {
    const index = child.parent?.children.indexOf(child) ?? -1
    if (index >= 0) child.parent.children.splice(index, 1)
  },
  setText(node, text) {
    node.text = text
  },
  setElementText(node, text) {
    node.text = text
    node.children = []
  },
  parentNode(node) {
    return node.parent
  },
  nextSibling(node) {
    const siblings = node.parent?.children || []
    return siblings[siblings.indexOf(node) + 1] || null
  },
  patchProp(node, key, _previous, value) {
    node.props[key] = value
  }
})

function findNodes(node, predicate, result = []) {
  if (predicate(node)) result.push(node)
  for (const child of node.children || []) findNodes(child, predicate, result)
  return result
}

test('解析入口仅为可用技能生成引用草稿，不发送请求', async () => {
  const file = new URL('../../src/components/ChatWelcome.vue', import.meta.url)
  const { descriptor } = parse(readFileSync(file, 'utf8'))
  const compiled = compileScript(descriptor, { id: 'report-parser-test', inlineTemplate: true })
  const temporary = fileURLToPath(
    new URL(`../../.report-parser-${pid}.mjs`, import.meta.url)
  )
  writeFileSync(
    temporary,
    compiled.content.replace('@/utils/mention_token', './src/utils/mention_token.js')
  )
  try {
    const { default: Component } = await import(pathToFileURL(temporary).href)
    for (const available of [false, true]) {
      const events = []
      const root = createHostNode('root')
      const app = renderer.createApp({
        render: () =>
          h(Component, {
            skills: available ? [{ slug: 'tax-inspection-report-parser' }] : [{ slug: 'other' }],
            onPrompt: (value) => events.push(value)
          })
      })
      app.mount(root)
      const section = findNodes(root, (node) => node.props.class === 'skill-entry')[0]
      const button = findNodes(section, (node) => node.type === 'button')[0]
      assert.equal(button.props.disabled, !available)
      button.props.onClick()
      assert.equal(events.length, available ? 1 : 0)
      if (available) {
        assert.ok(events[0].startsWith('@skill:tax-inspection-report-parser '))
        assert.match(events[0], /上传或粘贴正文/)
      }
      app.unmount()
    }
  } finally {
    unlinkSync(temporary)
  }
})
