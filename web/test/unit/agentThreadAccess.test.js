import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { resolveAuthorizedThread } from '../../src/utils/agentThreadAccess.js'

test('已知线程直接复用列表事实，缺失线程通过历史读取确认归属', async () => {
  const listed = { id: 'thread-a', agent_id: 'employee-a' }
  let reads = 0
  assert.equal(
    await resolveAuthorizedThread('thread-a', [listed], async () => {
      reads += 1
    }),
    listed
  )
  assert.equal(reads, 0)

  const restored = { id: 'thread-b', agent_id: 'employee-b' }
  assert.equal(
    await resolveAuthorizedThread('thread-b', [], async () => {
      reads += 1
      return { thread: restored }
    }),
    restored
  )
  assert.equal(reads, 1)
  assert.equal(
    await resolveAuthorizedThread('thread-c', [], async () => ({ thread: restored })),
    null
  )
})

test('消费端搜索和深链接按员工范围读取会话', () => {
  const searchSource = readFileSync(
    new URL('../../src/components/GlobalSearchModal.vue', import.meta.url),
    'utf8'
  )
  const chatSource = readFileSync(
    new URL('../../src/components/AgentChatComponent.vue', import.meta.url),
    'utf8'
  )
  assert.match(searchSource, /threadApi\.searchThreads\(query, \{\s*agentId: props\.agentId/)
  assert.match(searchSource, /watch\(\s*\(\) => props\.agentId,[\s\S]*?resetState\(\)/)
  assert.match(chatSource, /resolveAuthorizedThread\(\s*threadId,[\s\S]*?agentApi\.getAgentHistory/)
  const routeHandler = chatSource.slice(
    chatSource.indexOf('const selectThreadFromRoute'),
    chatSource.indexOf('const handleSendMessage')
  )
  assert.match(routeHandler, /await agentStore\.selectAgent\(targetThread\.agent_id\)/)
  assert.match(routeHandler, /if \(consumerChat\.value\) chatThreadsStore\.setAgentScope\(targetThread\.agent_id\)/)
  assert.ok(
    routeHandler.indexOf('chatThreadsStore.setAgentScope(targetThread.agent_id)') <
      routeHandler.indexOf('await loadChatsList()'),
    'history recovery must scope the thread store before the employee thread-list request'
  )
  assert.match(chatSource, /const scopedAgentId = chatThreadsStore\.activeAgentId/)
})
