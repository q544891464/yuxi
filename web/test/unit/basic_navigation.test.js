import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createRouter, createMemoryHistory } from 'vue-router'
import { resolvePostLoginRedirect, sanitizeRedirect } from '../../src/utils/oidcAutoStart.js'

const source = readFileSync(new URL('../../src/router/index.js', import.meta.url), 'utf8')
  .replace(/\r\n/g, '\n')
  .replace(/^import .*\n/gm, '')
  .replace('import.meta.env.BASE_URL', "''")
  .replace('export default router', 'return router')

function createTestRouter(userStore, { defaultAgentId = null, agents = [] } = {}) {
  const stubPages = (routes) =>
    routes.map((route) => ({
      ...route,
      ...(route.component ? { component: { render: () => null } } : {}),
      ...(route.children ? { children: stubPages(route.children) } : {})
    }))
  const factory = new Function(
    'createRouter',
    'createWebHistory',
    'useUserStore',
    'userConfigApi',
    'agentApi',
    'resolveDefaultEmployee',
    'sanitizeRedirect',
    'document',
    'PLATFORM_NAME',
    source
  )
  return factory(
    (config) => createRouter({ ...config, routes: stubPages(config.routes) }),
    createMemoryHistory,
    () => userStore,
    { get: async () => ({ default_agent_id: defaultAgentId }) },
    { getAgents: async () => ({ agents }) },
    (slug, items) =>
      items.find((item) => !item.is_subagent && (item.slug || item.id) === slug) || null,
    sanitizeRedirect,
    { title: '' },
    '智能数字员工平台'
  )
}

test('无有效默认员工时根路径进入聊天，员工选择页仍可显式打开', async () => {
  const router = createTestRouter({ token: 'test', userId: 1, isLoggedIn: true, isAdmin: true })
  await router.push('/')
  assert.equal(router.currentRoute.value.name, 'ChatComp')
  await router.push('/employees')
  assert.equal(router.currentRoute.value.name, 'EmployeeSquare')
  await router.push('/chat?agent_id=helper')
  assert.equal(router.currentRoute.value.name, 'ChatComp')
  assert.equal(router.currentRoute.value.query.agent_id, 'helper')
  for (const path of ['/choose-assistant', '/access-unavailable']) {
    await router.push(path)
    assert.equal(router.currentRoute.value.name, 'NotFound', path)
  }
  await router.push('/chat/ducha')
  assert.equal(router.currentRoute.value.path, '/chat')
  await router.push('/extensions')
  assert.equal(router.currentRoute.value.name, 'ExtensionsComp')
})

test('根路径仅对当前可见主员工应用个人默认值', async () => {
  const user = { token: 'test', userId: 1, isLoggedIn: true, isAdmin: false }
  const router = createTestRouter(user, {
    defaultAgentId: 'helper',
    agents: [
      { id: 'helper', slug: 'helper' },
      { id: 'child', slug: 'helper', is_subagent: true }
    ]
  })
  await router.push('/')
  assert.equal(router.currentRoute.value.path, '/chat')
  assert.equal(router.currentRoute.value.query.agent_id, 'helper')

  const invalidRouter = createTestRouter(user, {
    defaultAgentId: 'child',
    agents: [{ id: 'child', slug: 'child', is_subagent: true }]
  })
  await invalidRouter.push('/')
  assert.equal(invalidRouter.currentRoute.value.name, 'ChatComp')
})

test('未登录访问聊天详情进入登录，普通用户不能进入管理员页面', async () => {
  const user = { token: '', userId: null, isLoggedIn: false, isAdmin: false }
  const router = createTestRouter(user)
  await router.push('/chat/thread-1')
  assert.equal(router.currentRoute.value.path, '/login')
  assert.equal(router.currentRoute.value.query.redirect, '/chat/thread-1')
  Object.assign(user, { token: 'test', userId: 2, isLoggedIn: true })
  await router.push('/agent')
  assert.equal(router.currentRoute.value.path, '/chat')
  await router.push('/chat/thread-1')
  assert.equal(router.currentRoute.value.name, 'ChatCompWithThreadId')
})

test('合法登录回跳仍保留，分享登录 hash 交给登录页处理', async () => {
  const router = createTestRouter({ token: 'test', userId: 1, isLoggedIn: true, isAdmin: true })
  await router.push('/login')
  assert.equal(router.currentRoute.value.name, 'ChatComp')
  await router.push('/login?redirect=/workspace')
  assert.equal(router.currentRoute.value.path, '/workspace')
  await router.push('/login#key=example')
  assert.equal(router.currentRoute.value.path, '/login')
  assert.equal(router.currentRoute.value.hash, '#key=example')
})

test('密码、分享和 OIDC 登录保持统一根入口并保留安全的显式目标', () => {
  assert.equal(resolvePostLoginRedirect(undefined), '/')
  assert.equal(
    resolvePostLoginRedirect('/chat/thread-1?agent_id=helper'),
    '/chat/thread-1?agent_id=helper'
  )
  assert.equal(resolvePostLoginRedirect('//outside.example'), '/')

  const loginSource = readFileSync(
    new URL('../../src/views/LoginView.vue', import.meta.url),
    'utf8'
  )
  const callbackSource = readFileSync(
    new URL('../../src/views/OIDCCallbackView.vue', import.meta.url),
    'utf8'
  )
  assert.match(loginSource, /router\.push\(redirectPath\)/)
  assert.match(
    loginSource,
    /window\.location\.replace\(resolvePostLoginRedirect\(route\.query\.redirect\)\)/
  )
  assert.match(
    callbackSource,
    /resolvePostLoginRedirect\(sessionStorage\.getItem\('oidc_redirect'\)\)/
  )
})

test('消费端知识库保留布局，消费端总览仅管理员可访问', async () => {
  const user = { token: 'test', userId: 1, isLoggedIn: true, isAdmin: false }
  const router = createTestRouter(user)
  await router.push('/chat/knowledge')
  assert.equal(router.currentRoute.value.name, 'ConsumerKnowledge')
  assert.equal(router.currentRoute.value.meta.consumerChat, true)
  await router.push('/chat/knowledge/visible-kb')
  assert.equal(router.currentRoute.value.name, 'ConsumerKnowledgeBaseDetail')
  await router.push('/chat/dashboard')
  assert.equal(router.currentRoute.value.name, 'ChatComp')
  user.isAdmin = true
  await router.push('/chat/dashboard')
  assert.equal(router.currentRoute.value.name, 'ConsumerDashboard')
  assert.equal(router.currentRoute.value.meta.consumerChat, true)
})

test('业务配置与详情页保持前台外壳，只有管理工作台使用后台布局', async () => {
  const user = { token: 'test', userId: 1, isLoggedIn: true, isAdmin: true }
  const router = createTestRouter(user)
  for (const path of [
    '/employees',
    '/agent-manage',
    '/agent-manage?tab=providers',
    '/extensions',
    '/extensions?tab=knowledge',
    '/extensions/skill/example',
    '/extensions/mcp/example',
    '/extensions/knowledgebase/example',
    '/extensions/knowledgebase/example/evaluation/dataset',
    '/workspace',
    '/dashboard'
  ]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.fullPath, path)
    assert.equal(router.currentRoute.value.meta.consumerChat, true, path)
  }
  for (const path of ['/agent', '/agent/thread-1']) {
    await router.push(path)
    assert.notEqual(router.currentRoute.value.meta.consumerChat, true, path)
  }
  user.isAdmin = false
  for (const path of ['/extensions/skill/example', '/agent-manage', '/workspace']) {
    await router.push(path)
    assert.equal(router.currentRoute.value.fullPath, path)
    assert.equal(router.currentRoute.value.meta.consumerChat, true, path)
  }
  for (const path of [
    '/agent',
    '/dashboard',
    '/extensions/mcp/example',
    '/extensions/knowledgebase/example/evaluation/dataset'
  ]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, '/chat', path)
  }
})
