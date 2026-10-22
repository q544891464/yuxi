/** 读取可访问 Skill 接口返回的数据列表并丢弃无效条目。 */
export function normalizeAccessibleSkills(response) {
  const items = response?.data
  if (!Array.isArray(items)) return []
  return items.filter(
    (skill) => skill && typeof skill === 'object' && typeof skill.slug === 'string' && skill.slug
  )
}
