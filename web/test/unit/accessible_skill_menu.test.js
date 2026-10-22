import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { normalizeAccessibleSkills } from '../../src/utils/accessibleSkills.js'

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
