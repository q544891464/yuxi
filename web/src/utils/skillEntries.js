import { formatMentionToken } from './mention_token.js'

export const INSPECTION_KB_ID = 'kb_a2rvesuax2'

/** 展开业务配置，保留可调用的完整技能分组。 */
export function flattenSkillEntries(nodes = []) {
  return nodes.flatMap((node) => [node, ...flattenSkillEntries(node.children || [])])
}

export function findSkillEntry(id, nodes) {
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
