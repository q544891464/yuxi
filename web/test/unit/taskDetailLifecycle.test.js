import assert from 'node:assert/strict'
import test from 'node:test'
import { createRenderer, nextTick, reactive, ssrContextKey } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createServer } from 'vite'

/** 控制真实组件请求的完成顺序。 */
function deferred() {
  let resolve
  let reject
  const promise = new Promise((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

test('任务详情从接口读取，切换、关闭、退出后拒绝旧响应，当前文件异常保留历史', async () => {
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  let app
  try {
    const { default: Component } = await server.ssrLoadModule('/src/components/TaskDetailModal.vue')
    const { useUserStore } = await server.ssrLoadModule('/src/stores/user.js')
    const { taskerApi } = await server.ssrLoadModule('/src/apis/tasker.js')
    const { documentApi } = await server.ssrLoadModule('/src/apis/knowledge_api.js')
    const pinia = createPinia()
    const user = useUserStore(pinia)
    user.token = 'test-session'
    user.userRole = 'admin'
    const props = reactive({ taskId: 'first' })
    const requests = []
    taskerApi.fetchTaskDetail = (id) => {
      const response = deferred()
      requests.push({ id, ...response })
      return response.promise
    }
    let state
    const emitted = []
    const renderer = createRenderer({
      createComment: () => ({}),
      insert() {},
      remove() {},
      parentNode: () => null,
      nextSibling: () => null
    })
    app = renderer.createApp({
      setup() {
        state = Component.setup(props, { expose() {}, emit: (event) => emitted.push(event) })
        return () => null
      }
    })
    app.use(pinia)
    app.provide(ssrContextKey, {})
    app.use(createRouter({ history: createMemoryHistory(), routes: [] }))
    app.mount({})
    assert.equal(requests[0].id, 'first')
    props.taskId = 'second'
    assert.equal(requests[1].id, 'second')
    const historical = {
      id: 'second',
      payload: { kb_id: 'kb' },
      result: { items: [{ status: 'failed' }] }
    }
    requests[1].resolve({ task: historical })
    await nextTick()
    requests[0].resolve({ task: { id: 'first' } })
    await nextTick()
    assert.deepEqual(state.task.value, historical)

    documentApi.getDocumentBasicInfo = async () => ({ status: 'failed', message: 'storage error' })
    await state.loadCurrentFile('file')
    assert.ok(state.fileError.value.includes('无法读取'))
    assert.equal(state.currentFile.value, null)
    assert.deepEqual(state.task.value.result, historical.result)
    const fileResponse = deferred()
    documentApi.getDocumentBasicInfo = () => fileResponse.promise
    const fileLoading = state.loadCurrentFile('file')
    const refreshing = state.loadTask()
    fileResponse.resolve({ file_id: 'file', status: 'indexed' })
    await fileLoading
    assert.equal(state.currentFile.value, null)
    requests[2].resolve({ task: historical })
    await refreshing

    const failedRefresh = state.loadTask()
    requests.at(-1).reject(new Error('读取失败'))
    await failedRefresh
    assert.equal(state.error.value, '读取失败')
    assert.deepEqual(state.task.value.result, historical.result)

    const beforeLogout = state.loadTask()
    const oldSession = requests.at(-1)
    user.logout()
    oldSession.resolve({ task: historical })
    await beforeLogout
    assert.equal(state.task.value, null)
    assert.ok(emitted.includes('close'))
    user.userRole = 'admin'
    user.token = 'next-session'
    const lastResponse = requests.at(-1)
    app.unmount()
    app = null
    lastResponse.resolve({ task: historical })
    await nextTick()
    assert.equal(state.task.value, null)
  } finally {
    app?.unmount()
    await server.close()
  }
})
