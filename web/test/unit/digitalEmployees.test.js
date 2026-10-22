import assert from 'node:assert/strict'
import test from 'node:test'
import { resolveDefaultEmployee, searchEmployees } from '../../src/utils/digitalEmployees.js'
import { employeeTaskPurpose, getEmployeeTaskGuide } from '../../src/utils/employeeTaskGuidance.js'

const employees = [
  { id: 'assistant', slug: 'assistant', name: '系统助手', description: '通用问答' },
  { id: 'planner', slug: 'planner', name: '计划助手', description: '整理项目任务' },
  { id: 'child', slug: 'child', name: '子助手', is_subagent: true }
]

test('默认员工只匹配可见主员工，已失效标识返回空', () => {
  assert.equal(resolveDefaultEmployee('planner', employees), employees[1])
  assert.equal(resolveDefaultEmployee('child', employees), null)
  assert.equal(resolveDefaultEmployee('deleted', employees), null)
})

test('员工搜索匹配名称与用途且始终排除子员工', () => {
  assert.deepEqual(searchEmployees(employees, '项目'), [employees[1]])
  assert.deepEqual(searchEmployees(employees, '子助手'), [])
  assert.equal(searchEmployees(employees, '  ').length, 2)
})

test('只为服务端已核对的员工展示示例，同名自建与配置变更保留自身说明', () => {
  const custom = { slug: 'custom', name: '智能助手', description: '专属职责' }
  assert.equal(employeeTaskPurpose(custom), '专属职责')
  assert.deepEqual(getEmployeeTaskGuide(custom, {}, {}).examples, [])
  assert.equal(
    getEmployeeTaskGuide({ ...custom, slug: 'default-chatbot' }, {}, {}).examples.length,
    0
  )
  const assistant = { ...custom, slug: 'default-chatbot', starter_task_profile: 'default-chatbot' }
  assert.equal(getEmployeeTaskGuide(assistant, {}, {}).examples.length, 2)
  assert.equal(getEmployeeTaskGuide(assistant, { system_prompt: '被改写' }, {}).examples.length, 0)
  assert.equal(getEmployeeTaskGuide(null, {}, {}).examples.length, 0)
})

test('研究示例要求员工启用与账号可访问资源同时满足，未知或部分加载不算就绪', () => {
  const agent = { slug: 'deep-research', starter_task_profile: 'deep-research' }
  const config = { skills: ['deep-research'], subagents: ['research-explorer', 'fact-verifier'] }
  const items = {
    skills: { options: [{ key: 'deep-research' }], default: 'all' },
    subagents: { options: [{ key: 'research-explorer' }, { key: 'fact-verifier' }] }
  }
  assert.equal(getEmployeeTaskGuide(agent, config, items).examples.length, 2)
  assert.equal(getEmployeeTaskGuide(agent, { ...config, skills: [] }, items).examples.length, 0)
  assert.equal(
    getEmployeeTaskGuide(agent, config, { ...items, skills: { options: [] } }).examples.length,
    0
  )
  assert.equal(getEmployeeTaskGuide(agent, { ...config, subagents: [] }, items).examples.length, 0)
  assert.equal(
    getEmployeeTaskGuide(agent, config, {
      ...items,
      subagents: { options: [{ key: 'research-explorer' }] }
    }).examples.length,
    0
  )
  assert.equal(getEmployeeTaskGuide(agent, config).examples.length, 0)
})
