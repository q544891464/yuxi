import { formatMentionToken } from './mention_token.js'

export const CREATE_SKILL_INTENT = 'create-personal-skill'
export const CREATOR_SKILL_SLUG = 'skill-creator-v2'

/** 在保留现有输入的同时引用技能，空草稿才填入引导提示。 */
export function withSkillDraft(input, skill) {
  const current = String(input || '')
  const token = formatMentionToken('skill', skill.slug)
  if (current.includes(token)) return current
  const prompt =
    skill.slug === CREATOR_SKILL_SLUG
      ? '请引导我创建技能，先确认用途、输入材料和预期输出，再逐步完成创建与验证。'
      : `请使用${skill.display_name || skill.name || skill.slug}协助我完成工作，请先说明需要的材料。`
  return `${token} ${current.trim() ? current : prompt}`
}

/** 侧栏入口只预填当前数字员工已启用的技能。 */
export function canReferenceSkill(skill, enabledSkills) {
  return Boolean(skill?.slug && enabledSkills?.some((item) => item.slug === skill.slug))
}
