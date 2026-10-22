import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  normalizeAccessibleSkills,
  resolveNavigationTree,
  findNavigationEntry,
  getEmployeeEnabledSkills
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

test('员工已保存技能选择优先，未设置时沿用 schema 默认值', () => {
  assert.deepEqual(
    getEmployeeEnabledSkills({ configurable_items: { skills: { default: 'all' } } }),
    'all'
  )
  assert.deepEqual(
    getEmployeeEnabledSkills({
      config_json: { context: { skills: [] } },
      configurable_items: { skills: { default: 'all' } }
    }),
    []
  )
})

test('技能标题可隐藏，运行技能菜单不提供个人技能创建入口', () => {
  const source = readFileSync(
    new URL('../../src/components/AccessibleSkillMenu.vue', import.meta.url),
    'utf8'
  )
  assert.match(source, /showTitle: \{ type: Boolean, default: true \}/)
  assert.match(source, /<span v-if="showTitle">技能<\/span>/)
  assert.doesNotMatch(source, /class="add-skill"/)
  assert.match(source, /\.menu-heading-compact\s*\{\s*justify-content: flex-start;/)
})

test('员工配置只接受技能 slug，禁用技能始终隐藏', async () => {
  const server = await (await import('vite')).createServer({
    server: { middlewareMode: true },
    appType: 'custom'
  })
  try {
    const { filterEnabledAgentSkills } = await server.ssrLoadModule('/src/utils/accessibleSkills.js')
    const skills = [
      { slug: 'enabled' },
      { slug: 'disabled', enabled: false },
      { slug: 'personal', source_scope: 'personal' }
    ]
    assert.deepEqual(filterEnabledAgentSkills(skills, ['enabled', 'disabled', 'personal']), [
      skills[0],
      skills[2]
    ])
    assert.deepEqual(filterEnabledAgentSkills(skills, [{ slug: 'enabled' }]), [])
    assert.deepEqual(filterEnabledAgentSkills(skills, 'all'), [skills[0], skills[2]])
  } finally {
    await server.close()
  }
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
