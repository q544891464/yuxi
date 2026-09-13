/** 从已鉴权的资源列表生成首页展示，不将请求失败解释为零。 */
export function summarizeChatWelcome([knowledge, agents, skills]) {
  const databases = knowledge.status === 'fulfilled' ? knowledge.value?.databases : null
  const agentList = agents.status === 'fulfilled' ? agents.value?.agents : null
  const skillList = skills.status === 'fulfilled' ? skills.value?.data : null
  const knowledgeReady = Array.isArray(databases) && !knowledge.value.message
  const questions = knowledgeReady
    ? [
        ...new Set(
          databases
            .flatMap((db) => (Array.isArray(db.sample_questions) ? db.sample_questions : []))
            .filter((q) => typeof q === 'string')
            .map((q) => q.trim())
            .filter(Boolean)
        )
      ].slice(0, 4)
    : []
  return {
    questions,
    fileCount:
      knowledgeReady &&
      databases.every((db) => Number.isSafeInteger(db.file_count) && db.file_count >= 0)
        ? databases.reduce((sum, db) => sum + db.file_count, 0)
        : null,
    subagentCount: Array.isArray(agentList)
      ? agentList.filter((agent) => agent.is_subagent).length
      : null,
    skillCount: Array.isArray(skillList) ? skillList.length : null
  }
}
