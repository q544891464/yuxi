/** 读取可访问 Skill 接口返回的数据列表并丢弃无效条目。 */
export function normalizeAccessibleSkills(response) {
  const items = response?.data
  if (!Array.isArray(items)) return []
  return items.filter(
    (skill) => skill && typeof skill === 'object' && typeof skill.slug === 'string' && skill.slug
  )
}

/** 只保留数字员工明确启用且当前用户可访问的技能。 */
export function filterEnabledAgentSkills(skills, configuredSkills) {
  const enabledSkills = skills.filter((skill) => skill.enabled !== false)
  if (configuredSkills === 'all') return enabledSkills
  if (!Array.isArray(configuredSkills)) return []
  const enabled = new Set(configuredSkills.filter((skill) => typeof skill === 'string'))
  return enabledSkills.filter((skill) => enabled.has(skill.slug))
}

/** 已保存选择优先，缺少时沿用技能字段的 schema 默认值。 */
export function getEmployeeEnabledSkills(detail) {
  return detail?.config_json?.context?.skills ?? detail?.configurable_items?.skills?.default ?? []
}

/** 菜单绑定只解析当前可访问的共享技能，个人覆盖版本独立展示。 */
export function resolveNavigationTree(tree, skills) {
  const available = new Map(
    skills
      .filter((skill) => skill.source_scope !== 'personal' && skill.enabled !== false)
      .map((skill) => [skill.slug, skill])
  )
  const visit = (nodes) =>
    nodes.flatMap((node) => {
      const children = visit(node.children || [])
      const skill = available.get(node.skillSlug)
      return skill || children.length ? [{ ...node, skill, children }] : []
    })
  return visit(tree)
}

/** 入口 id 与 slug 同时匹配，配置不能通过 URL 注入另一项提示词。 */
export function findNavigationEntry(tree, id, slug) {
  for (const node of tree) {
    if (node.id === id && node.skillSlug === slug) return node
    const found = findNavigationEntry(node.children || [], id, slug)
    if (found) return found
  }
  return null
}
