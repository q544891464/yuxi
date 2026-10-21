/** 仅将当前可见主智能体作为个人默认入口。 */
export const resolveDefaultEmployee = (slug, agents = []) => {
  if (!slug) return null
  return (
    agents.find((agent) => !agent.is_subagent && (agent.slug || agent.id) === slug) || null
  )
}

/** 按员工名称和用途筛选当前用户可见的主智能体。 */
export const searchEmployees = (agents = [], keyword = '') => {
  const normalizedKeyword = String(keyword).trim().toLocaleLowerCase()
  const employees = agents.filter((agent) => !agent.is_subagent)
  if (!normalizedKeyword) return employees
  return employees.filter((agent) =>
    [agent.name, agent.description].some((value) =>
      String(value || '').toLocaleLowerCase().includes(normalizedKeyword)
    )
  )
}
