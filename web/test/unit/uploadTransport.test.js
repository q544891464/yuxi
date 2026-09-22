import test from 'node:test'
import assert from 'node:assert/strict'
import { uploadTransport } from '../../src/apis/uploadTransport.js'

class FakeXHR {
  static latest
  constructor() {
    FakeXHR.latest = this
    this.upload = {}
    this.headers = {}
  }
  open() {}
  setRequestHeader(name, value) {
    this.headers[name] = value
  }
  getResponseHeader() {
    return 'application/json'
  }
  send(body) {
    this.body = body
  }
  abort() {
    this.aborted = true
    this.onabort?.()
  }
}

test('字节进度100%不提前完成；HTTP错误保留给统一边界', async () => {
  globalThis.XMLHttpRequest = FakeXHR
  const progress = []
  let completed = false
  const request = uploadTransport(
    '/upload',
    { headers: { Authorization: 'test' }, body: 'file' },
    (n) => progress.push(n)
  )
  request.then(() => {
    completed = true
  })
  const xhr = FakeXHR.latest
  xhr.upload.onprogress({ lengthComputable: true, loaded: 5, total: 10 })
  xhr.upload.onprogress({ lengthComputable: true, loaded: 10, total: 10 })
  await Promise.resolve()
  assert.deepEqual(progress, [50, 100])
  assert.equal(completed, false)
  assert.equal(xhr.headers.Authorization, 'test')
  xhr.status = 413
  xhr.responseText = '{}'
  xhr.onload()
  const response = await request
  assert.equal(response.status, 413)
  assert.equal(response.ok, false)
})

test('取消终止传输；提前取消不会发送', async () => {
  globalThis.XMLHttpRequest = FakeXHR
  const controller = new AbortController()
  const request = uploadTransport('/upload', { signal: controller.signal }, () => {})
  const xhr = FakeXHR.latest
  controller.abort()
  await assert.rejects(request, { name: 'AbortError' })
  assert.equal(xhr.aborted, true)
  await assert.rejects(
    uploadTransport('/upload', { signal: controller.signal }, () => {}),
    { name: 'AbortError' }
  )
  assert.equal(FakeXHR.latest.body, undefined)
})
