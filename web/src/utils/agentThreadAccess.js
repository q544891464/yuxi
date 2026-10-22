/** 缺少列表条目时通过有权限校验的历史接口确认线程所属员工。 */
export async function resolveAuthorizedThread(threadId, threads, readThreadHistory) {
  const listedThread = threads.find((thread) => thread.id === threadId)
  if (listedThread) return listedThread
  const snapshot = await readThreadHistory(threadId)
  return snapshot?.thread?.id === threadId ? snapshot.thread : null
}
