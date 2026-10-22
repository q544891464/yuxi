import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  normalizeAccessibleSkills,
  resolveNavigationTree,
  findNavigationEntry
} from '../../src/utils/accessibleSkills.js'

test('技能菜单保留接口返回的可访问技能，并忽略无有效 slug 的条目', () => {
  const permitted = { slug: 'research', name: '资料检索', description: '检索资料' }
  assert.deepEqual(
    normalizeAccessibleSkills({ data: [permitted, null, { name: '无标识技能' }, { slug: '' }] }),
    [permitted]
  )
})

test('技能接口数据缺失时菜单为空', () => {
  assert.deepEqual(normalizeAccessibleSkills(null), [])
  assert.deepEqual(normalizeAccessibleSkills({ data: {} }), [])
})

test('技能标题可隐藏，但添加技能入口仍保留', () => {
  const source = readFileSync(
    new URL('../../src/components/AccessibleSkillMenu.vue', import.meta.url),
    'utf8'
  )
  assert.match(source, /showTitle: \{ type: Boolean, default: true \}/)
  assert.match(source, /<span v-if="showTitle">技能<\/span>/)
  assert.match(source, /class="add-skill"[^>]*@click="\$emit\('create'\)"/)
  assert.match(source, /\.menu-heading-compact\s*\{\s*justify-content: flex-start;/)
})

test('共享菜单解析保留配置顺序，并把无权限父绑定降为分组', () => {
  const tree = [
    {
      id: 'group',
      name: '办公',
      skillSlug: 'unavailable',
      children: [
        { id: 'second', name: '摘要', skillSlug: 'summary', children: [] },
        { id: 'first', name: '报告', skillSlug: 'report', children: [] },
        { id: 'personal', name: '个人版本', skillSlug: 'private', children: [] }
      ]
    }
  ]
  const resolved = resolveNavigationTree(tree, [
    { slug: 'report', source_scope: 'shared' },
    { slug: 'summary', source_scope: 'shared' },
    { slug: 'private', source_scope: 'personal' }
  ])
  assert.equal(resolved[0].skill, undefined)
  assert.deepEqual(
    resolved[0].children.map((n) => n.id),
    ['second', 'first']
  )
  assert.deepEqual(resolveNavigationTree(tree, []), [])
})

test('同一技能的多个配置入口使用各自提示词，URL 不能串用其他绑定', () => {
  const tree = [
    {
      id: 'group',
      name: '办公',
      children: [
        { id: 'summary', skillSlug: 'report', prompt: '生成摘要' },
        { id: 'full', skillSlug: 'report', prompt: '生成完整报告' }
      ]
    }
  ]
  assert.equal(findNavigationEntry(tree, 'summary', 'report').prompt, '生成摘要')
  assert.equal(findNavigationEntry(tree, 'full', 'report').prompt, '生成完整报告')
  assert.equal(findNavigationEntry(tree, 'full', 'private'), null)
  assert.equal(findNavigationEntry(tree, 'removed', 'report'), null)
})
