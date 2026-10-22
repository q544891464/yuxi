import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { createServer } from 'vite'

test('侧栏菜单区分未配置与空菜单，账号切换后迟到响应不可覆盖新配置，失败可重试', async (t) => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: { getItem: () => '', setItem() {}, removeItem() {} }
  })
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  setActivePinia(createPinia())
  try {
    const { useSkillNavigationStore } = await server.ssrLoadModule('/src/stores/skillNavigation.js')
    const { useUserStore } = await server.ssrLoadModule('/src/stores/user.js')
    const { skillNavigationApi } = await server.ssrLoadModule('/src/apis/skill_navigation_api.js')
    const pending = []
    t.mock.method(
      skillNavigationApi,
      'get',
      () => new Promise((resolve, reject) => pending.push({ resolve, reject }))
    )
    const user = useUserStore()
    user.userId = 1
    user.userRole = 'admin'
    const store = useSkillNavigationStore()
    const first = store.load()
    const duplicate = store.load()
    assert.equal(pending.length, 1)
    pending[0].resolve({ revision: 0, tree: [], configured: false })
    await Promise.all([first, duplicate])
    assert.equal(store.configured, false)
    assert.equal(store.loaded, true)
    await store.load()
    assert.equal(pending.length, 1)
    store.invalidate()
    const old = store.load()
    user.userId = 2
    assert.equal(store.loaded, false)
    assert.deepEqual(store.tree, [])
    const fresh = store.load()
    pending[1].resolve({ revision: 4, tree: [{ id: 'old-user-private' }], configured: true })
    await old
    assert.equal(store.loading, true)
    assert.deepEqual(store.tree, [])
    pending[2].resolve({ revision: 2, tree: [], configured: true })
    await fresh
    assert.equal(store.configured, true)
    assert.deepEqual(store.tree, [])
    assert.equal(store.loading, false)
    store.invalidate()
    const failed = store.load()
    pending[3].reject(new Error('offline'))
    await assert.rejects(failed, /offline/)
    assert.equal(store.loaded, false)
    assert.ok(store.error)
    const retry = store.load()
    pending[4].resolve({ revision: 3, tree: [{ id: 'current-user' }], configured: true })
    await retry
    assert.equal(store.error, '')
    assert.equal(store.tree[0].id, 'current-user')
  } finally {
    await server.close()
  }
})
