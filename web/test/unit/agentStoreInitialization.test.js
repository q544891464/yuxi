import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { createServer } from 'vite'

test('并行调用 initialize 都等待同一轮 Agent Store 初始化', async () => {
  const previousStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: { getItem: () => null, setItem() {}, removeItem() {} }
  })
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  setActivePinia(createPinia())
  try {
    const { useAgentStore } = await server.ssrLoadModule('/src/stores/agent.js')
    const { agentApi, databaseApi, toolApi } = await server.ssrLoadModule('/src/apis/index.js')
    let resolveAgents
    agentApi.getAgents = () => new Promise((resolve) => { resolveAgents = resolve })
    databaseApi.getAccessibleDatabases = async () => ({ databases: [] })
    toolApi.getTools = async () => ({ data: [] })
    const store = useAgentStore()

    const firstInitialization = store.initialize()
    const secondInitialization = store.initialize()
    let secondFinished = false
    void secondInitialization.then(() => { secondFinished = true })
    await Promise.resolve()

    assert.equal(store.isInitialized, false)
    assert.equal(secondFinished, false)
    resolveAgents({ agents: [] })
    await Promise.all([firstInitialization, secondInitialization])

    assert.equal(store.isInitialized, true)
  } finally {
    await server.close()
    if (previousStorage) Object.defineProperty(globalThis, 'localStorage', previousStorage)
    else delete globalThis.localStorage
  }
})
