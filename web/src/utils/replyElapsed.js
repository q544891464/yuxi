/** 同一运行首次进入回复加载状态时记录绝对起点，重连不会覆盖。 */
export const markReplyLoadingStarted = (threadState, timingKey, now = Date.now()) => {
  if (!threadState) return null
  if (
    threadState.replyTimingKey !== timingKey ||
    !Number.isFinite(threadState.replyStartedAtMs)
  ) {
    threadState.replyTimingKey = timingKey
    threadState.replyStartedAtMs = now
  }
  threadState.replyLoadingVisible = true
  return threadState.replyStartedAtMs
}

/** 根据绝对起点计算秒数，使页面暂停刷新期间仍按真实时间推进。 */
export const getReplyElapsedSeconds = (startedAtMs, now = Date.now()) => {
  if (!Number.isFinite(startedAtMs) || !Number.isFinite(now)) return 0
  return Math.max(0, Math.floor((now - startedAtMs) / 1000))
}
