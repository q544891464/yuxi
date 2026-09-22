import test from 'node:test'
import assert from 'node:assert/strict'
import { documentRequestId } from '../../src/utils/documentRequestId.js'

test('HTTP 内网页面缺少 randomUUID 时仍可生成独立的创建标识', () => {
  const random = globalThis.crypto
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: { getRandomValues: random.getRandomValues.bind(random) }
  })
  try {
    const ids = Array.from({ length: 100 }, documentRequestId)
    assert.equal(new Set(ids).size, ids.length)
    for (const id of ids)
      assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  } finally {
    Object.defineProperty(globalThis, 'crypto', original)
  }
})
