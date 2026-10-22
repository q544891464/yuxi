import assert from 'node:assert/strict'
import test from 'node:test'
import { canReferenceSkill, withSkillDraft } from '../../src/utils/skillDraft.js'

test('技能启动预填真实引用和中文用途', () => {
  const draft = withSkillDraft('', { slug: 'report-writer', display_name: '报告生成' })
  assert.match(draft, /^@skill:report-writer /)
  assert.ok(draft.includes('报告生成'))
})

test('切换技能保留用户草稿且重复点击不重复引用', () => {
  const skill = { slug: 'report-writer', name: '报告生成' }
  const draft = withSkillDraft('请检查附表的汇总。', skill)
  assert.ok(draft.endsWith('请检查附表的汇总。'))
  assert.equal(withSkillDraft(draft, skill), draft)
})

test('创建技能使用现有 skill-creator-v2 引用而非导航管理后台', () => {
  const draft = withSkillDraft('', { slug: 'skill-creator-v2' })
  assert.match(draft, /^@skill:skill-creator-v2 /)
  assert.ok(draft.includes('创建技能'))
})

test('可访问但未被当前员工启用的技能不能预填', () => {
  const skill = { slug: 'report-writer' }
  assert.equal(canReferenceSkill(skill, [{ slug: 'report-writer' }]), true)
  assert.equal(canReferenceSkill(skill, [{ slug: 'skill-creator-v2' }]), false)
  assert.equal(canReferenceSkill(skill, []), false)
  assert.equal(canReferenceSkill(skill, undefined), false)
})

test('空草稿使用管理员预设指令，已有用户文本继续保留', () => {
  const skill = { slug: 'report', name: '报告' }
  assert.equal(
    withSkillDraft('', skill, '请先校验数据，再生成报告。'),
    '@skill:report 请先校验数据，再生成报告。'
  )
  assert.equal(withSkillDraft('保留我的要求', skill, '模板指令'), '@skill:report 保留我的要求')
})
