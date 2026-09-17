const names = {
  'audit-report-writer': '撰写稽查报告',
  'ai-assisted-review': '撰写审理文书',
  'vat-surtax-recalc': '申报数据处理'
}

/** 业务技能使用中文展示名，调用标识保持原值。 */
export function getSkillDisplayName(value, fallback = value) {
  const key = String(value || '').trim().toLowerCase().replace(/[\s_]+/g, '-')
  return names[key] || fallback || ''
}
