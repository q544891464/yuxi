import assert from 'node:assert/strict'
import test from 'node:test'
import { availableAssistants, assistantEntry } from '../../src/utils/digitalAssistants.js'

test('数字人列表严格来自页面权限，督查与稽查素材独立', () => {
  assert.deepEqual(
    availableAssistants(['/chat']).map((item) => item.path),
    ['/chat']
  )
  assert.deepEqual(
    availableAssistants(['/chat/ducha']).map((item) => item.path),
    ['/chat/ducha']
  )
  assert.deepEqual(availableAssistants(undefined), [])
  assert.equal(availableAssistants(null).length, 2)
  assert.notEqual(availableAssistants(null)[0].image, availableAssistants(null)[1].image)
  assert.equal(assistantEntry({ pages: ['/agent'], home: '/agent' }), '/agent')
})
