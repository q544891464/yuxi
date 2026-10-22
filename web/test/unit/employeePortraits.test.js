import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  DEFAULT_EMPLOYEE_PORTRAITS,
  getDefaultEmployeePortrait
} from '../../src/utils/employeePortraits.js'

test('默认主员工与自建员工使用不同的随应用发布的人物图', () => {
  assert.equal(getDefaultEmployeePortrait(null), '/employees/assistant.png')
  assert.equal(getDefaultEmployeePortrait({ slug: 'default-chatbot' }), '/employees/assistant.png')
  assert.equal(getDefaultEmployeePortrait({ slug: 'deep-research' }), '/employees/researcher.png')
  assert.equal(getDefaultEmployeePortrait({ id: 'custom-employee' }), '/employees/coordinator.png')
})

test('默认形象均为真实带透明通道的 PNG，不依赖外网或 SVG 占位', () => {
  for (const item of DEFAULT_EMPLOYEE_PORTRAITS) {
    const bytes = readFileSync(new URL('../../public' + item.src, import.meta.url))
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    assert.equal(bytes[25], 6, item.src + ' must be RGBA')
  }
})
