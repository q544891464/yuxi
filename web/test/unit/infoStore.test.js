import assert from 'node:assert/strict'
import test from 'node:test'

import { createPinia, setActivePinia } from 'pinia'
import { createServer } from 'vite'

test('调试模式读取受限 LocalStorage 时降级为关闭', async () => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem() {
        throw new DOMException('blocked', 'SecurityError')
      },
      setItem() {},
      removeItem() {}
    }
  })
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  setActivePinia(createPinia())
  try {
    const { useInfoStore } = await server.ssrLoadModule('/src/stores/info.js')
    const store = useInfoStore()

    assert.equal(store.debugMode, false)
  } finally {
    await server.close()
  }
})

test('品牌配置合并并发读取，成功缓存，失败与强制刷新可重试', async (t) => {
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  setActivePinia(createPinia())
  try {
    const { useInfoStore } = await server.ssrLoadModule('/src/stores/info.js')
    const { brandApi } = await server.ssrLoadModule('/src/apis/system_api.js')
    const store = useInfoStore()
    const pending = []
    t.mock.method(brandApi, 'getInfoConfig', () => new Promise((resolve) => pending.push(resolve)))
    const first = store.loadInfoConfig()
    const second = store.loadInfoConfig()
    assert.equal(pending.length, 1)
    pending[0]({ success: true, data: { branding: { name: 'Test' } } })
    assert.deepEqual(await first, { branding: { name: 'Test' } })
    assert.deepEqual(await second, { branding: { name: 'Test' } })
    assert.equal(store.branding.name, 'Test')
    await store.loadInfoConfig()
    assert.equal(pending.length, 1)
    const forced = store.loadInfoConfig(true)
    assert.equal(pending.length, 2)
    pending[1]({ success: false })
    assert.equal(await forced, null)
    const retry = store.loadInfoConfig(true)
    assert.equal(pending.length, 3)
    pending[2]({ success: true, data: { branding: { name: 'New' } } })
    await retry
    assert.equal(store.branding.name, 'New')
    assert.equal(store.isLoading, false)
  } finally {
    await server.close()
  }
})

test('旧默认品牌名称在前端配置入口显示为当前平台名', async (t) => {
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  setActivePinia(createPinia())
  try {
    const { useInfoStore } = await server.ssrLoadModule('/src/stores/info.js')
    const { brandApi } = await server.ssrLoadModule('/src/apis/system_api.js')
    const store = useInfoStore()
    t.mock.method(brandApi, 'getInfoConfig', async () => ({
      success: true,
      data: {
        organization: { name: 'Yuxi', logo: '/favicon.svg' },
        branding: { name: 'Yuxi', title: 'Yuxi 智能助手' }
      }
    }))
    await store.loadInfoConfig()

    assert.equal(store.organization.name, '智能数字员工平台')
    assert.equal(store.organization.logo, '/favicon.svg')
    assert.equal(store.branding.name, '智能数字员工平台')
    assert.equal(store.branding.title, '智能数字员工平台')
  } finally {
    await server.close()
  }
})
