import { formatMentionToken } from './mention_token.js'

export const INSPECTION_KB_ID = 'kb_a2rvesuax2'

export const SKILL_CREATOR_ENTRY = Object.freeze({
  id: 'create-personal-skill',
  label: '添加技能',
  skillSlug: 'skill-creator-v2',
  skillDisplayName: '技能创建助手',
  inputHint: '请描述希望新增的能力、适用场景、输入材料和期望输出。',
  outputHint: '通过对话澄清需求并创建可复用的个人技能。',
  presetPrompt:
    '请引导我创建一个新的个人技能。先询问技能用途、使用场景、输入材料、期望输出和约束条件；信息充分后再创建技能，并说明如何验证和调用。',
  children: []
})

/** 展开业务配置，保留可调用的完整技能分组。 */
export function flattenSkillEntries(nodes = []) {
  return nodes.flatMap((node) => [node, ...flattenSkillEntries(node.children || [])])
}

export function findSkillEntry(id, nodes) {
  if (id === SKILL_CREATOR_ENTRY.id) return SKILL_CREATOR_ENTRY
  return flattenSkillEntries(nodes).find((item) => item.id === id) || null
}

/** 只匹配配置中指定的真实 slug，重复结果显式不可用。 */
export function resolveEntrySkill(entry, skills = []) {
  if (!entry) return null
  const normalize = (value) =>
    String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, '-')
  const name = normalize(entry.skillSlug)
  const matches = skills.filter(
    (skill) => skill.enabled !== false && normalize(skill.slug) === name
  )
  return matches.length === 1 && matches[0].slug ? matches[0] : null
}

/** 引用文本与手动 @ 选择沿用同一协议。 */
export function buildSkillEntryPrompt(entry, skill) {
  return `${formatMentionToken('skill', skill.slug)} ${entry.presetPrompt}`
}
