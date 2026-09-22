import assert from 'node:assert/strict'
import test from 'node:test'
import { canVisitPage } from '../../src/utils/pageAccess.js'

test('页面菜单按完整边界区分督查、稽查和嵌入内容', () => {
  for (const path of [
    '/chat',
    '/chat/duchax',
    '/extensions',
    '/chat/knowledge/kb',
    '/chat/dashboard'
  ]) {
    assert.equal(canVisitPage(['/chat/ducha'], path), false, path)
  }
  assert.equal(canVisitPage(['/chat/ducha'], '/chat/ducha/thread'), true)
  assert.equal(canVisitPage(['/extensions'], '/chat/knowledge/kb'), true)
  assert.equal(canVisitPage(['/chat'], '/chat/ducha'), false)
  assert.equal(canVisitPage(undefined, '/chat'), false)
  assert.equal(canVisitPage(null, '/agent'), true)
})
