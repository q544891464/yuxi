import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createRouter, createMemoryHistory } from 'vue-router'
import { sanitizeRedirect } from '../../src/utils/oidcAutoStart.js'

const source = readFileSync(new URL('../../src/router/index.js', import.meta.url), 'utf8')
  .replace(/\r\n/g, '\n')
  .replace(/^import .*\n/gm, '')
  .replace('import.meta.env.BASE_URL', "''")
  .replace('export default router', 'return router')

// 使用实际路由表和守卫，仅替换页面渲染与用户接口，验证入口的完整导航结果。
function createTestRouter(userStore) {
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
    'useAgentStore',
    'sanitizeRedirect',
    source
  )
  return factory(
    (config) => createRouter({ ...config, routes: stubPages(config.routes) }),
    createMemoryHistory,
    () => userStore,
    () => {
      throw new Error('入口导航不应加载智能体')
    },
    sanitizeRedirect
  )
}

test('首页按认证状态进入登录页或智能体，过期会话不能停留在工作区', async (t) => {
  const previousStorage = globalThis.sessionStorage
  globalThis.sessionStorage = { setItem() {} }
  try {
    for (const scenario of [
      { name: '未登录', token: null, userId: null, isLoggedIn: false, expected: '/login' },
      {
        name: '已登录',
        token: 'test-token',
        userId: 1,
        isLoggedIn: true,
        isAdmin: true,
        expected: '/agent'
      },
      { name: '过期会话', token: 'expired', userId: null, isLoggedIn: true, expected: '/login' }
    ]) {
      await t.test(scenario.name, async () => {
        const user = {
          ...scenario,
          async getCurrentUser() {
            throw new Error('expired session')
          },
          logout() {
            this.token = null
            this.isLoggedIn = false
          }
        }
        const router = createTestRouter(user)
        await router.push('/')
        assert.equal(router.currentRoute.value.path, scenario.expected)
        assert.ok(!router.currentRoute.value.matched.some((route) => route.name === 'Home'))
      })
    }
  } finally {
    if (previousStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previousStorage
  }
})

test('已登录访问登录页默认进入智能体，同时保留合法的深链接', async () => {
  const router = createTestRouter({
    token: 'test-token',
    userId: 1,
    isLoggedIn: true,
    isAdmin: true
  })
  await router.push('/login')
  assert.equal(router.currentRoute.value.path, '/agent')
  await router.push('/login?redirect=/workspace')
  assert.equal(router.currentRoute.value.path, '/workspace')
})

// 通过真实路由执行直接访问与登录回跳，防止普通用户绕过入口分流。
test('普通用户入口和管理员工作台访问隔离', async () => {
  const router = createTestRouter({
    token: 'test-token',
    userId: 2,
    isLoggedIn: true,
    isAdmin: false
  })
  for (const path of [
    '/',
    '/login',
    '/agent',
    '/agent/thread-1',
    '/login?redirect=/agent/thread-1'
  ]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, '/chat', path)
    assert.equal(router.currentRoute.value.meta.consumerChat, true)
  }
  await router.push('/chat/thread-1')
  assert.equal(router.currentRoute.value.params.thread_id, 'thread-1')
  assert.equal(router.currentRoute.value.name, 'ChatCompWithThreadId')
})

test('管理员可选择用户界面并保留工作台深链接', async () => {
  const router = createTestRouter({
    token: 'test-token',
    userId: 1,
    isLoggedIn: true,
    isAdmin: true
  })
  await router.push('/agent/thread-1')
  assert.equal(router.currentRoute.value.name, 'AgentCompWithThreadId')
  await router.push('/chat')
  assert.equal(router.currentRoute.value.name, 'ChatComp')
})
