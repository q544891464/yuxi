import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createNavigationEntryId,
  navigationRows,
  navigationTree,
  descendantIds,
  moveNavigationRow
} from '../../src/utils/skillNavigationEditor.js'

test('添加入口不依赖仅安全上下文可用的 randomUUID', (t) => {
  t.mock.method(globalThis.crypto, 'randomUUID', () => {
    throw new Error('HTTP 页面不能使用 randomUUID')
  })
  const ids = Array.from({ length: 100 }, createNavigationEntryId)
  assert.equal(new Set(ids).size, 100)
  for (const id of ids) assert.match(id, /^entry-[0-9a-f]{32}$/)
})

test('调整同级顺序、移动子项和删除子树保留其他入口与绑定', () => {
  const original = [
    { id: 'a', skillSlug: 'one', children: [{ id: 'b', skillSlug: 'two', children: [] }] },
    { id: 'c', skillSlug: 'three', children: [] }
  ]
  const rows = navigationRows(original)
  assert.deepEqual(navigationTree(rows), original)
  moveNavigationRow(rows, 'c', -1)
  assert.deepEqual(
    navigationTree(rows).map((n) => n.id),
    ['c', 'a']
  )
  rows.find((n) => n.id === 'b').parentId = 'c'
  assert.equal(navigationTree(rows)[0].children[0].skillSlug, 'two')
  const deleted = new Set(['c', ...descendantIds(rows, 'c')])
  assert.deepEqual(navigationTree(rows.filter((n) => !deleted.has(n.id))), [
    { id: 'a', skillSlug: 'one', children: [] }
  ])
})

test('循环、孤立节点和第四层拒绝保存；空树可明确保存', () => {
  assert.deepEqual(navigationTree([]), [])
  assert.throws(() => navigationTree([{ id: 'a', parentId: 'a' }]), /循环/)
  assert.throws(() => navigationTree([{ id: 'a', parentId: 'missing' }]), /父级/)
  assert.throws(
    () =>
      navigationTree(
        ['a', 'b', 'c', 'd'].map((id, i, ids) => ({ id, parentId: i ? ids[i - 1] : '' }))
      ),
    /三级/
  )
})
