import assert from 'node:assert/strict'
import test from 'node:test'
import { summarizeChatWelcome } from '../../src/utils/chatWelcome.js'
const ok = (value) => ({ status: 'fulfilled', value })
const failed = { status: 'rejected', reason: new Error('unavailable') }

test('首页读取知识库问题并去重，文件夹和主智能体不计入统计', () => {
  const result = summarizeChatWelcome([
    ok({
      databases: [
        { file_count: 12, folder_count: 7, sample_questions: [' 申报流程？ ', '政策调整？'] },
        {
          file_count: 3,
          folder_count: 2,
          sample_questions: ['申报流程？', '', '地方优惠？', '材料要求？', '第五问？']
        }
      ]
    }),
    ok({ agents: [{ is_subagent: false }, { is_subagent: true }, { is_subagent: true }] }),
    ok({ data: [{ name: 'one' }, { name: 'two' }] })
  ])
  assert.deepEqual(result, {
    questions: ['申报流程？', '政策调整？', '地方优惠？', '材料要求？'],
    fileCount: 15,
    subagentCount: 2,
    skillCount: 2
  })
})
test('真实空资源显示零，不补写虚构示例问题', () => {
  assert.deepEqual(
    summarizeChatWelcome([ok({ databases: [] }), ok({ agents: [] }), ok({ data: [] })]),
    { questions: [], fileCount: 0, subagentCount: 0, skillCount: 0 }
  )
})
test('请求失败和服务端失败空列表显示未知，其他成功统计保留', () => {
  const result = summarizeChatWelcome([
    ok({ message: 'failed', databases: [] }),
    failed,
    ok({ data: [{ name: 'one' }] })
  ])
  assert.deepEqual(result, { questions: [], fileCount: null, subagentCount: null, skillCount: 1 })
  assert.equal(summarizeChatWelcome([failed, failed, failed]).fileCount, null)
})

test('不完整的文件统计不会显示 NaN 或虚构数量', () => {
  const result = summarizeChatWelcome([
    ok({ databases: [{ sample_questions: [null, '有效问题？'] }] }),
    ok({ agents: [] }),
    ok({ data: [] })
  ])
  assert.equal(result.fileCount, null)
  assert.deepEqual(result.questions, ['有效问题？'])
})

test('HTTP 成功但缺失响应体时展示未知并允许重试', () => {
  for (const value of [null, undefined]) {
    assert.deepEqual(summarizeChatWelcome([ok(value), ok(value), ok(value)]), {
      questions: [],
      fileCount: null,
      subagentCount: null,
      skillCount: null
    })
  }
})
