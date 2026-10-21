import assert from 'node:assert/strict'
import test from 'node:test'
import { resolveDefaultEmployee, searchEmployees } from '../../src/utils/digitalEmployees.js'

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
