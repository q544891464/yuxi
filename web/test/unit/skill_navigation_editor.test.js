import assert from 'node:assert/strict'
import test from 'node:test'
import {
  descendantIds,
  moveNavigationRow,
  navigationRows,
  navigationTree
} from '../../src/utils/skillNavigationEditor.js'

test('编辑行保持嵌套顺序并序列化回不含编辑字段的导航树', () => {
  const tree = [
    {
      id: 'group',
      name: '常用',
      skillSlug: '',
      material: '',
      result: '',
      prompt: '',
      visibleRoles: ['user'],
      children: [
        {
          id: 'entry',
          name: '技能甲',
          skillSlug: 'skill-a',
          material: '材料',
          result: '用途',
          prompt: '提示',
          visibleRoles: ['user'],
          children: []
        }
      ]
    },
    {
      id: 'entry-b',
      name: '技能乙',
      skillSlug: 'skill-b',
      material: '材料',
      result: '用途',
      prompt: '提示',
      visibleRoles: ['admin'],
      children: []
    }
  ]
  const rows = navigationRows(tree)
  assert.deepEqual(
    rows.map(({ id, parentId, kind }) => [id, parentId, kind]),
    [
      ['group', '', 'group'],
      ['entry', 'group', 'entry'],
      ['entry-b', '', 'entry']
    ]
  )
  assert.deepEqual(navigationTree(rows), tree)
  assert.deepEqual(descendantIds(rows, 'group'), ['entry'])
})

test('排序只交换同级项，树序列化拒绝过深和孤立节点', () => {
  const rows = navigationRows([
    { id: 'a', name: 'A', skillSlug: '', children: [] },
    { id: 'b', name: 'B', skillSlug: '', children: [] }
  ])
  moveNavigationRow(rows, 'b', -1)
  assert.deepEqual(
    navigationTree(rows).map((node) => node.id),
    ['b', 'a']
  )
  assert.throws(
    () =>
      navigationTree([
        { id: 'a', parentId: '', skillSlug: '' },
        { id: 'b', parentId: 'a', skillSlug: '' },
        { id: 'c', parentId: 'b', skillSlug: '' },
        { id: 'd', parentId: 'c', skillSlug: '' }
      ]),
    /最多三级/
  )
  assert.throws(() => navigationTree([{ id: 'orphan', parentId: 'missing' }]), /无效父级/)
})
