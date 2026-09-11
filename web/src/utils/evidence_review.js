const risks = new Set(['low', 'medium', 'high'])
const summaryKeys = [
  'violation_count',
  'fact_count',
  'sufficient_count',
  'basically_sufficient_count',
  'doubtful_count',
  'insufficient_count',
  'high_risk_count'
]
export const sufficiencyLabels = {
  sufficient: '证据充分',
  basically_sufficient: '基本充分',
  doubtful: '存在疑点',
  insufficient: '证据不足'
}
export const riskLabels = { low: '低风险', medium: '中风险', high: '高风险' }

/** 校验结果卡片依赖的文本字段，残缺数据交给通用结果展示。 */
const hasTextFields = (value, fields) =>
  value && fields.every((field) => typeof value[field] === 'string')
const isTextList = (value) =>
  Array.isArray(value) && value.every((item) => typeof item === 'string')

export function parseEvidenceReview(value) {
  // task 的线程提示属于既有协议；只剥离固定前缀，不从任意正文中猜测 JSON。
  let result = value
  if (typeof value === 'string') {
    const text = value.replace(/^> 子智能体线程 ID: [^\n]+\n\n---\n\n/, '')
    try {
      result = JSON.parse(text)
    } catch {
      return null
    }
  }
  if (
    !result ||
    result.review_type !== 'fact_evidence_review' ||
    !['pass', 'warning', 'risk'].includes(result.overall_status) ||
    !result.summary ||
    !summaryKeys.every(
      (key) => Number.isInteger(result.summary[key]) && result.summary[key] >= 0
    ) ||
    ![
      'violation_reviews',
      'evidence_conflicts',
      'evidence_gaps',
      'review_findings',
      'limitations'
    ].every((key) => Array.isArray(result[key]))
  )
    return null
  const valid =
    result.violation_reviews.every(
      (violation) =>
        hasTextFields(violation, [
          'violation_id',
          'violation_name',
          'inspection_fact',
          'overall_conclusion'
        ]) &&
        Array.isArray(violation.fact_reviews) &&
        violation.fact_reviews.length > 0 &&
        risks.has(violation.overall_risk) &&
        violation.fact_reviews.every(
          (fact) =>
            hasTextFields(fact, ['fact_id', 'fact', 'evidence_analysis', 'recommendation']) &&
            Object.hasOwn(sufficiencyLabels, fact.conclusion) &&
            risks.has(fact.risk_level) &&
            isTextList(fact.issues) &&
            isTextList(fact.missing_evidence) &&
            Array.isArray(fact.evidence) &&
            fact.evidence.every((item) =>
              hasTextFields(item, ['evidence_id', 'name', 'type', 'proves', 'relation'])
            )
        )
    ) &&
    result.review_findings.every(
      (item) =>
        hasTextFields(item, ['title', 'description', 'recommendation']) &&
        risks.has(item.risk_level)
    ) &&
    result.evidence_conflicts.every(
      (item) =>
        hasTextFields(item, ['evidence_a', 'evidence_b', 'conflict', 'impact']) &&
        risks.has(item.risk_level)
    ) &&
    result.evidence_gaps.every((item) =>
      hasTextFields(item, ['fact', 'missing', 'impact', 'recommendation'])
    ) &&
    isTextList(result.limitations)
  return valid ? result : null
}
