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
    'sanitizeRedirect',
    'document',
    source
  )
  return factory(
    (config) => createRouter({ ...config, routes: stubPages(config.routes) }),
    createMemoryHistory,
    () => userStore,
    sanitizeRedirect,
    { title: '' }
  )
}

test('Basic 入口统一进入聊天，旧业务页面不再可达', async () => {
  const router = createTestRouter({ token: 'test', userId: 1, isLoggedIn: true, isAdmin: true })
  await router.push('/')
  assert.equal(router.currentRoute.value.path, '/chat')
  for (const path of ['/choose-assistant', '/access-unavailable']) {
    await router.push(path)
    assert.equal(router.currentRoute.value.name, 'NotFound', path)
  }
  await router.push('/chat/ducha')
  assert.equal(router.currentRoute.value.path, '/chat')
  await router.push('/extensions')
  assert.equal(router.currentRoute.value.name, 'ExtensionsComp')
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
  await router.push('/login?redirect=/workspace')
  assert.equal(router.currentRoute.value.path, '/workspace')
  await router.push('/login#key=example')
  assert.equal(router.currentRoute.value.path, '/login')
  assert.equal(router.currentRoute.value.hash, '#key=example')
})
