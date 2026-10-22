import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import test from 'node:test'
import { createMemoryHistory, createRouter } from 'vue-router'

const source = await readFile(new URL('../../src/views/AgentView.vue', import.meta.url), 'utf8')
const syncStart = source.indexOf('const syncSelectedThreadFromRoute = async () => {')
assert.ok(syncStart >= 0)
const syncHandler = source.slice(syncStart, source.indexOf('\nconst consumeRouteAgentSelection', syncStart))
const threadChangeStart = source.indexOf('const handleThreadChange = (threadId) => {')
assert.ok(threadChangeStart >= 0)
const threadChangeHandler = source.slice(
  threadChangeStart,
  source.indexOf('\nconst agentQuickSwitchOptions', threadChangeStart)
)
const start = source.indexOf('const consumeRouteAgentSelection = async () => {')
assert.ok(start >= 0)
const handler = source.slice(start, source.indexOf('\nwatch(', start))

/** 控制异步步骤完成时机，不依赖定时器或网络速度。 */
function deferred() {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}

/** 执行页面原函数，使用真实内存路由记录离页和返回的身份变化。 */
async function setup(path = '/chat?agent_id=employee-a&project_id=project-a') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/chat', name: 'ChatComp', component: {} },
      { path: '/agent', name: 'AgentComp', component: {} },
      { path: '/employees', component: {} },
      { path: '/agent-manage', component: {} },
      { path: '/knowledge', component: {} }
    ]
  })
  await router.push(path)
  const selected = []
  const errors = []
  const route = new Proxy({}, { get: (_, key) => router.currentRoute.value[key] })
  const agentStore = {
    isInitialized: true,
    initialize: async () => {
      agentStore.isInitialized = true
    },
    selectAgent: async (id) => {
      selected.push(id)
    }
  }
  const chatComponentRef = { value: { selectThreadFromRoute: async () => true } }
  const consume = vm.runInNewContext(`${handler}\nconsumeRouteAgentSelection`, {
    route,
    router,
    agentStore,
    chatComponentRef,
    entryRoute: {
      get value() {
        return route.name === 'AgentComp' ? 'AgentComp' : 'ChatComp'
      }
    },
    getRouteAgentId: () => route.query.agent_id || '',
    getRouteThreadId: () => route.params.thread_id || '',
    nextTick: async () => {},
    handleChatError: (error) => errors.push(error.message)
  })
  return { router, agentStore, chatComponentRef, selected, errors, consume }
}

test('当前页面选择员工后移除一次性参数，保留项目', async () => {
  const ctx = await setup()
  await ctx.consume()
  assert.deepEqual(ctx.selected, ['employee-a'])
  assert.equal(ctx.router.currentRoute.value.fullPath, '/chat?project_id=project-a')
})

for (const stage of ['initialize', 'thread', 'agent']) {
  test(`在 ${stage} 等待期间离页，旧任务不能覆盖导航`, async () => {
    const ctx = await setup()
    const entered = deferred()
    const release = deferred()
    const delayed = async () => {
      entered.resolve()
      await release.promise
      ctx.agentStore.isInitialized = true
      return true
    }
    if (stage === 'initialize') {
      ctx.agentStore.isInitialized = false
      ctx.agentStore.initialize = delayed
    } else if (stage === 'thread') {
      ctx.chatComponentRef.value.selectThreadFromRoute = delayed
    } else ctx.agentStore.selectAgent = delayed
    const pending = ctx.consume()
    await entered.promise
    await ctx.router.push('/agent-manage')
    release.resolve()
    await pending
    assert.equal(ctx.router.currentRoute.value.fullPath, '/agent-manage')
    assert.deepEqual(ctx.selected, [])
  })
}

test('离页再返回同一 URL，旧任务仍不能清理新页面的员工参数', async () => {
  const ctx = await setup()
  const entered = deferred()
  const release = deferred()
  ctx.agentStore.selectAgent = async () => {
    entered.resolve()
    await release.promise
  }
  const originalPath = ctx.router.currentRoute.value.fullPath
  const pending = ctx.consume()
  await entered.promise
  await ctx.router.push('/employees')
  await ctx.router.push(originalPath)
  release.resolve()
  await pending
  assert.equal(ctx.router.currentRoute.value.fullPath, originalPath)
})

test('过期选择失败不干扰新页面，当前选择失败仍显示错误', async () => {
  for (const leave of [false, true]) {
    const ctx = await setup()
    const entered = deferred()
    const release = deferred()
    ctx.agentStore.selectAgent = async () => {
      entered.resolve()
      await release.promise
      throw new Error('员工不可用')
    }
    const pending = ctx.consume()
    await entered.promise
    if (leave) await ctx.router.push('/knowledge')
    release.resolve()
    await pending
    assert.deepEqual(ctx.errors, leave ? [] : ['员工不可用'])
    assert.equal(ctx.router.currentRoute.value.path, leave ? '/knowledge' : '/chat')
  }
})

test('缓存聊天组件不消费其他页面上的同名参数', async () => {
  const ctx = await setup('/agent-manage?agent_id=employee-a')
  await ctx.consume()
  assert.equal(ctx.router.currentRoute.value.fullPath, '/agent-manage?agent_id=employee-a')
  assert.deepEqual(ctx.selected, [])
})

test('深链在员工 Store 初始化完成前保持路由，并等待后再读取线程', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/chat/:thread_id?', name: 'ChatComp', component: {} }]
  })
  await router.push('/chat/employee-b-thread')
  const route = new Proxy({}, { get: (_, key) => router.currentRoute.value[key] })
  const initialize = deferred()
  const reads = []
  const agentStore = {
    isInitialized: false,
    initialize: () => initialize.promise
  }
  const chatComponentRef = {
    value: {
      selectThreadFromRoute: async (threadId) => {
        reads.push(threadId)
        return true
      }
    }
  }
  const syncingRouteThread = { value: false }
  const sync = vm.runInNewContext(`${syncHandler}\nsyncSelectedThreadFromRoute`, {
    route,
    router,
    agentStore,
    chatComponentRef,
    syncingRouteThread,
    routeSyncVersion: 0,
    entryRoute: { value: 'ChatComp' },
    getRouteThreadId: () => route.params.thread_id || '',
    handleChatError: () => {}
  })
  const handleThreadChange = vm.runInNewContext(`${threadChangeHandler}\nhandleThreadChange`, {
    route,
    router,
    syncingRouteThread,
    entryRoute: { value: 'ChatComp' }
  })

  const pending = sync()
  assert.equal(syncingRouteThread.value, true)
  assert.deepEqual(reads, [])
  handleThreadChange('')
  assert.equal(router.currentRoute.value.fullPath, '/chat/employee-b-thread')
  initialize.resolve()
  agentStore.isInitialized = true
  await pending

  assert.deepEqual(reads, ['employee-b-thread'])
  assert.equal(router.currentRoute.value.fullPath, '/chat/employee-b-thread')
  assert.equal(syncingRouteThread.value, false)
})
