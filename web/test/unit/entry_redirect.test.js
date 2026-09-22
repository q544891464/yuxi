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
function createTestRouter(
  userStore,
  pageAccess = {
    resolve: async () => ({
      allowed: true,
      home: userStore.isAdmin ? '/agent' : '/chat',
      pages: null
    })
  },
  getDuchaPage = async () => ({})
) {
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
    'pageAccessApi',
    'getDuchaPage',
    'document',
    source
  )
  return factory(
    (config) => createRouter({ ...config, routes: stubPages(config.routes) }),
    createMemoryHistory,
    () => userStore,
    () => {
      throw new Error('入口导航不应加载智能体')
    },
    sanitizeRedirect,
    pageAccess,
    getDuchaPage,
    { title: '' }
  )
}

test('受限督查角色登录和禁止地址回到督查页，保留督查对话详情', async () => {
  const user = { token: 'test', userId: 4, isLoggedIn: true, isAdmin: false }
  const router = createTestRouter(user, {
    resolve: async (path) => ({
      allowed: path === '/chat/ducha' || path.startsWith('/chat/ducha/'),
      home: '/chat/ducha',
      pages: ['/chat/ducha']
    })
  })
  for (const path of [
    '/login',
    '/chat',
    '/agent',
    '/workspace',
    '/extensions',
    '/chat/knowledge/kb',
    '/dashboard'
  ]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, '/chat/ducha')
  }
  await router.push('/chat/ducha/thread-1')
  assert.equal(router.currentRoute.value.name, 'DuchaChatCompWithThreadId')
  assert.deepEqual(user.allowedPages, ['/chat/ducha'])
})

test('页面权限读取失败显示重试页，不能进入工作区', async () => {
  const router = createTestRouter(
    { token: 'test', userId: 4, isLoggedIn: true },
    {
      resolve: async () => {
        throw Error('offline')
      }
    }
  )
  await router.push('/chat')
  assert.equal(router.currentRoute.value.path, '/access-unavailable')
  assert.equal(router.currentRoute.value.query.redirect, '/chat')
})

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

  await router.push('/login#key=yxshare_test')
  assert.equal(router.currentRoute.value.path, '/login')
  assert.equal(router.currentRoute.value.hash, '#key=yxshare_test')
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

test('未登录直达聊天及深链接不依赖会话存储，跳转登录并保留目标', async () => {
  const previousStorage = globalThis.sessionStorage
  globalThis.sessionStorage = {
    setItem() {
      throw new Error('SecurityError: storage blocked')
    }
  }
  try {
    for (const path of ['/chat', '/chat/thread-1?view=files']) {
      const router = createTestRouter({ token: '', isLoggedIn: false })
      await router.push(path)
      assert.equal(router.currentRoute.value.path, '/login')
      assert.equal(router.currentRoute.value.query.redirect, path)
    }
  } finally {
    if (previousStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previousStorage
  }
})

test('密码登录成功后不依赖会话存储，按角色或合法深链接进入工作区', async () => {
  const loginSource = readFileSync(
    new URL('../../src/views/LoginView.vue', import.meta.url),
    'utf8'
  )
  const handler = loginSource.slice(
    loginSource.indexOf('const handleLogin ='),
    loginSource.indexOf('const handleOIDCLogin =')
  )
  for (const scenario of [
    { isAdmin: true, redirect: undefined, expected: '/agent' },
    { isAdmin: false, redirect: undefined, expected: '/chat' },
    { isAdmin: false, redirect: '/chat/thread-1', expected: '/chat/thread-1' },
    { isAdmin: false, redirect: '//outside.example', expected: '/chat' }
  ]) {
    const destinations = []
    const errorMessage = { value: '' }
    const loading = { value: false }
    const dependencies = {
      isLocked: { value: false },
      ensureAgreementAccepted: () => true,
      clearLockCountdown() {},
      loading,
      errorMessage,
      loginForm: { loginId: 'test', password: 'test-only' },
      userStore: { isAdmin: scenario.isAdmin, async login() {} },
      route: { query: { redirect: scenario.redirect } },
      router: { push: (path) => destinations.push(path) },
      message: { success() {} },
      sanitizeRedirect,
      sessionStorage: new Proxy(
        {},
        {
          get() {
            throw new Error('SecurityError: storage blocked')
          }
        }
      )
    }
    const login = new Function(...Object.keys(dependencies), `${handler}; return handleLogin`)(
      ...Object.values(dependencies)
    )
    await login()
    assert.deepEqual(destinations, [scenario.expected])
    assert.equal(errorMessage.value, '')
    assert.equal(loading.value, false)
  }
})

test('督查入口服务失败进入重试页，不与受限首页循环跳转', async () => {
  const router = createTestRouter(
    { token: 'test', userId: 4, isLoggedIn: true },
    { resolve: async () => ({ allowed: true, home: '/chat/ducha', pages: ['/chat/ducha'] }) },
    async () => {
      throw Error('unavailable')
    }
  )
  await router.push('/chat/ducha')
  assert.equal(router.currentRoute.value.path, '/access-unavailable')
})

test('伪造分享登录 hash 不能绕过角色页面限制', async () => {
  const router = createTestRouter(
    { token: 'test', userId: 4, isLoggedIn: true, isAdmin: true },
    { resolve: async (path) => ({ allowed: path === '/chat', home: '/chat', pages: ['/chat'] }) }
  )
  for (const path of ['/agent#key=fake', '/dashboard#key=fake']) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, '/chat')
  }
})

test('已有用户信息的会话过期后直接回登录页', async () => {
  const user = { token: 'test', userId: 4, isLoggedIn: true }
  const router = createTestRouter(user, {
    resolve: async () => {
      user.isLoggedIn = false
      throw Object.assign(Error('expired'), { status: 401 })
    }
  })
  await router.push('/chat')
  assert.equal(router.currentRoute.value.path, '/login')
  assert.equal(router.currentRoute.value.query.redirect, '/chat')
})

test('配置首页覆盖默认角色入口，但保留允许的显式深链接', async () => {
  const router = createTestRouter(
    { token: 'test', userId: 4, isLoggedIn: true, isAdmin: true },
    {
      resolve: async (path) => ({
        allowed: path !== '/login',
        home: '/workspace',
        pages: ['/agent', '/workspace']
      })
    }
  )
  await router.push('/')
  assert.equal(router.currentRoute.value.path, '/workspace')
  await router.push('/login?redirect=/agent/thread-1')
  assert.equal(router.currentRoute.value.path, '/agent/thread-1')
})
