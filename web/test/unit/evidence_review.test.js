import assert from 'node:assert/strict'
import test from 'node:test'
import { parseEvidenceReview } from '../../src/utils/evidence_review.js'

const result = {
  review_type: 'fact_evidence_review',
  overall_status: 'risk',
  summary: {
    violation_count: 1,
    fact_count: 1,
    sufficient_count: 0,
    basically_sufficient_count: 0,
    doubtful_count: 0,
    insufficient_count: 1,
    high_risk_count: 1
  },
  violation_reviews: [
    {
      violation_id: 'V1',
      violation_name: '收入事项',
      inspection_fact: '收入100万元',
      overall_conclusion: '证据不足',
      overall_risk: 'high',
      fact_reviews: [
        {
          fact_id: 'F1',
          fact: '收入100万元',
          evidence_analysis: '缺少证据',
          recommendation: '补充流水',
          conclusion: 'insufficient',
          risk_level: 'high',
          evidence: [],
          issues: [],
          missing_evidence: []
        }
      ]
    }
  ],
  evidence_conflicts: [],
  evidence_gaps: [],
  review_findings: [],
  limitations: []
}

test('同步 task 和异步子任务结果均可解析', () => {
  assert.deepEqual(parseEvidenceReview(JSON.stringify(result)), result)
  assert.deepEqual(
    parseEvidenceReview(`> 子智能体线程 ID: child\n\n---\n\n${JSON.stringify(result)}`),
    result
  )
})

test('普通输出、未完成和残缺结构保留通用显示', () => {
  for (const value of [
    '分析中',
    '{',
    '{}',
    null,
    { ...result, violation_reviews: [null] },
    { ...result, evidence_conflicts: [null] },
    { ...result, limitations: null },
    {
      ...result,
      violation_reviews: [{ overall_risk: 'high', fact_reviews: [{ conclusion: '100%' }] }]
    }
  ]) {
    assert.equal(parseEvidenceReview(value), null)
  }
})

test('不从任意正文或伪造代码块中提取审查结果', () => {
  assert.equal(parseEvidenceReview(`普通说明\n${JSON.stringify(result)}`), null)
  assert.equal(parseEvidenceReview('```json\n' + JSON.stringify(result) + '\n```'), null)
})

test('不接受缺失或无效的汇总计数', () => {
  assert.equal(parseEvidenceReview({ ...result, summary: { fact_count: 1 } }), null)
  assert.equal(
    parseEvidenceReview({ ...result, summary: { ...result.summary, high_risk_count: -1 } }),
    null
  )
})

test('拒绝缺少标题、事实、分析或意见的嵌套结果', () => {
  for (const [target, fields] of [
    ['violation', ['violation_id', 'violation_name', 'inspection_fact', 'overall_conclusion']],
    ['fact', ['fact_id', 'fact', 'evidence_analysis', 'recommendation']]
  ]) {
    for (const field of fields) {
      const data = structuredClone(result)
      const violation = data.violation_reviews[0]
      delete (target === 'violation' ? violation : violation.fact_reviews[0])[field]
      assert.equal(parseEvidenceReview(data), null, field)
    }
  }
})
