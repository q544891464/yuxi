import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { createServer } from 'vite'

globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }

test('强制刷新不接受旧请求，切换身份清除旧菜单', async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  setActivePinia(createPinia())
  try {
    const { skillNavigationApi } = await server.ssrLoadModule('/src/apis/skill_navigation_api.js')
    const { useSkillNavigationStore } = await server.ssrLoadModule('/src/stores/skillNavigation.js')
    const { useUserStore } = await server.ssrLoadModule('/src/stores/user.js')
    const user = useUserStore()
    user.userId = 1
    user.userRole = 'admin'
    const pending = []
    skillNavigationApi.get = () => new Promise((resolve) => pending.push(resolve))
    const store = useSkillNavigationStore()
    const oldRequest = store.load()
    const refreshed = store.load(true)
    pending[1]({ revision: 2, nodes: [{ id: 'new' }] })
    await refreshed
    pending[0]({ revision: 1, nodes: [{ id: 'old' }] })
    await oldRequest
    assert.equal(store.nodes[0].id, 'new')
    assert.equal(store.revision, 2)
    const staleIdentity = store.load(true)
    user.userId = 2
    user.userRole = 'ducha'
    assert.deepEqual(store.nodes, [])
    pending[2]({ revision: 2, nodes: [{ id: 'admin-only' }] })
    await staleIdentity
    assert.deepEqual(store.nodes, [])
    assert.equal(store.loaded, false)
  } finally {
    await server.close()
  }
})
