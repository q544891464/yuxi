import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { createPinia, disposePinia, setActivePinia } from 'pinia'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer } from 'vite'

test('技能管理只装配当前身份允许的资源，非法 Tab 回到技能', async () => {
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
    plugins: [
      {
        name: 'management-child-stubs',
        load(id) {
          const name = id.match(
            /\/(SkillCardList|ToolsCardList|McpCardList|SkillNavigationSettings)\.vue$/
          )?.[1]
          if (name) return `<template><div data-panel="${name}" /></template>`
        }
      }
    ]
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  try {
    const { useUserStore } = await server.ssrLoadModule('/src/stores/user.js')
    const { default: Extensions } = await server.ssrLoadModule('/src/views/ExtensionsView.vue')
    const user = useUserStore()
    user.token = 'fixture'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/extensions', component: Extensions }]
    })
    /** 渲染真实管理页面，子面板以名称标记挂载结果。 */
    const render = async (role, tab = '') => {
      user.userRole = role
      await router.push({ path: '/extensions', query: tab ? { tab } : {} })
      return renderToString(createSSRApp(Extensions).use(pinia).use(router))
    }
    let html = await render('admin')
    assert.match(html, /技能管理/)
    assert.match(html, /data-panel="SkillCardList"/)
    assert.doesNotMatch(
      html,
      /智能体扩展|知识库|data-panel="(?:ToolsCardList|McpCardList|SkillNavigationSettings)"/
    )
    for (const [tab, panel] of [
      ['tools', 'ToolsCardList'],
      ['mcp', 'McpCardList'],
      ['navigation', 'SkillNavigationSettings']
    ]) {
      html = await render('admin', tab)
      assert.match(html, new RegExp(`data-panel="${panel}"`))
      assert.doesNotMatch(html, /data-panel="SkillCardList"/)
      html = await render('user', tab)
      assert.match(html, /data-panel="SkillCardList"/)
      assert.doesNotMatch(
        html,
        /侧栏技能|>工具<|>MCP<|data-panel="(?:ToolsCardList|McpCardList|SkillNavigationSettings)"/
      )
    }
    html = await render('admin', 'unknown')
    assert.match(html, /data-panel="SkillCardList"/)
  } finally {
    disposePinia(pinia)
    await server.close()
  }
})

test('知识库管理独立展示，导航和用户菜单不再包含管理工作台', () => {
  const read = (path) => readFileSync(new URL(`../../src/${path}`, import.meta.url), 'utf8')
  const knowledge = read('views/DataBaseView.vue')
  assert.match(knowledge, /title="知识库管理"/)
  assert.doesNotMatch(knowledge, /:tabs=|SkillCardList|ToolsCardList|McpCardList/)
  const layout = read('layouts/AppLayout.vue')
  assert.match(layout, /name: '知识库管理', path: '\/knowledge'/)
  assert.doesNotMatch(layout + read('components/UserInfoComponent.vue'), /管理工作台/)
  assert.match(
    read('views/DataBaseInfoView.vue'),
    /const backToDatabase = \(\) => \{\s*router.push\(\s*route.name === 'ConsumerKnowledgeBaseDetail' \|\| !userStore.isAdmin\s*\? \{ name: 'ConsumerKnowledge' \}\s*: \{ name: 'KnowledgeManage' \}/
  )
})
