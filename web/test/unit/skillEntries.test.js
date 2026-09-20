import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  flattenSkillEntries,
  findSkillEntry as findEntry,
  resolveEntrySkill,
  buildSkillEntryPrompt,
  SKILL_CREATOR_ENTRY
} from '../../src/utils/skillEntries.js'

const skillEntryTree = JSON.parse(
  readFileSync(
    new URL('../../../backend/package/yuxi/config/static/skill_navigation.json', import.meta.url),
    'utf8'
  )
)
const findSkillEntry = (id) => findEntry(id, skillEntryTree)

test('菜单保留图示层级，两个校验入口分别绑定报告和审理技能', () => {
  assert.deepEqual(
    skillEntryTree.map((item) => item.label),
    ['撰写稽查报告', '撰写审理文书']
  )
  assert.equal(
    flattenSkillEntries(skillEntryTree).filter((item) => !item.children?.length).length,
    11
  )
  assert.equal(findSkillEntry('inspection-check').skillSlug, 'audit-report-writer')
  assert.equal(findSkillEntry('review-check').skillSlug, 'ai-assisted-review')
  assert.deepEqual(
    findSkillEntry('case-nature').children.map((item) => item.label),
    ['重大案审', '一案双查', '黑名单', '移送公安']
  )
})

test('绑定实际返回的 slug 并生成标准技能引用，而不是猜测中文名称', () => {
  const entry = { ...findSkillEntry('declarations'), skillSlug: 'installed-vat-v2' }
  const actual = { slug: 'installed-vat-v2', name: 'Vat Surtax Recalc' }
  const skill = resolveEntrySkill(entry, [actual])
  assert.equal(skill, actual)
  assert.equal(buildSkillEntryPrompt(entry, skill).startsWith('@skill:installed-vat-v2 '), true)
  assert.match(buildSkillEntryPrompt(entry, skill), /净入库数据/)
  assert.match(entry.outputHint, /第二页汇总表/)
})

test('未开放、禁用和歧义技能均不可绑定，不静默选择其他技能', () => {
  const entry = findSkillEntry('review')
  assert.equal(resolveEntrySkill(entry, []), null)
  assert.equal(resolveEntrySkill(entry, [{ slug: 'other', name: 'Other' }]), null)
  assert.equal(
    resolveEntrySkill(entry, [{ slug: 'review', name: entry.skillSlug, enabled: false }]),
    null
  )
  assert.equal(
    resolveEntrySkill(entry, [
      { slug: 'a', name: entry.skillSlug },
      { slug: 'b', name: entry.skillSlug }
    ]),
    null
  )
  assert.equal(findSkillEntry('invalid'), null)
})

test('技能名允许大小写和分隔符差异，引用仍使用返回的原始标识', () => {
  const actual = { slug: 'ai-assisted-review', name: 'AI Assisted Review' }
  assert.equal(resolveEntrySkill(findSkillEntry('review-ledger'), [actual]), actual)
})

test('添加技能入口调用全局 skill-creator 并只准备引导草稿', () => {
  const entry = findEntry(SKILL_CREATOR_ENTRY.id, skillEntryTree)
  const skill = resolveEntrySkill(entry, [{ slug: 'skill-creator-v2', name: 'Skill Creator' }])
  assert.equal(entry, SKILL_CREATOR_ENTRY)
  assert.equal(skill.slug, 'skill-creator-v2')
  assert.match(buildSkillEntryPrompt(entry, skill), /^@skill:skill-creator-v2 /)
  assert.match(buildSkillEntryPrompt(entry, skill), /先询问技能用途/)
  assert.equal(resolveEntrySkill(entry, []), null)
})

import { getSkillDisplayName } from '../../src/utils/skillDisplayName.js'

test('技能中文展示不改变实际引用标识，历史引用也使用中文', () => {
  for (const [id, slug, label] of [
    ['inspection', 'audit-report-writer', '撰写稽查报告'],
    ['review', 'ai-assisted-review', '撰写审理文书'],
    ['declarations', 'vat-surtax-recalc', '申报数据处理']
  ]) {
    const entry = findSkillEntry(id)
    assert.equal(entry.skillDisplayName, label)
    assert.equal(getSkillDisplayName(entry.skillSlug), label)
    assert.ok(buildSkillEntryPrompt(entry, { slug }).startsWith(`@skill:${slug} `))
  }
  assert.equal(getSkillDisplayName('custom-skill', '自定义技能'), '自定义技能')
})
