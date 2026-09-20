import assert from 'node:assert/strict'
import test from 'node:test'

import { getReplyElapsedSeconds, markReplyLoadingStarted } from '../../src/utils/replyElapsed.js'

test('同一线程重连和切回时保留回复计时起点', () => {
  const threadState = { replyLoadingVisible: false, replyStartedAtMs: null }

  assert.equal(markReplyLoadingStarted(threadState, 'request-a', 10_000), 10_000)
  assert.equal(getReplyElapsedSeconds(threadState.replyStartedAtMs, 22_900), 12)

  assert.equal(markReplyLoadingStarted(threadState, 'request-a', 30_000), 10_000)
  assert.equal(getReplyElapsedSeconds(threadState.replyStartedAtMs, 35_500), 25)
})

test('新一轮回复和不同线程分别拥有自己的计时起点', () => {
  const firstThread = { replyLoadingVisible: false, replyStartedAtMs: 10_000 }
  const secondThread = { replyLoadingVisible: false, replyStartedAtMs: null }

  assert.equal(markReplyLoadingStarted(firstThread, 'request-a', 40_000), 40_000)
  assert.equal(markReplyLoadingStarted(secondThread, 'request-b', 50_000), 50_000)
  assert.equal(getReplyElapsedSeconds(firstThread.replyStartedAtMs, 55_000), 15)
  assert.equal(getReplyElapsedSeconds(secondThread.replyStartedAtMs, 55_000), 5)
})

test('队列中的下一次运行即使紧接旧运行也按新请求重新起算', () => {
  const threadState = { replyLoadingVisible: true }
  markReplyLoadingStarted(threadState, 'request-a', 1_000)

  assert.equal(markReplyLoadingStarted(threadState, 'request-b', 8_000), 8_000)
  assert.equal(threadState.replyTimingKey, 'request-b')
})

test('绝对时间计算处理无效起点与浏览器时钟回拨', () => {
  assert.equal(getReplyElapsedSeconds(null, 10_000), 0)
  assert.equal(getReplyElapsedSeconds(20_000, 10_000), 0)
})
