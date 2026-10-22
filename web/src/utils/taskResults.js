export const TASK_STATUS_CONFIG = {
  pending: { label: '等待中', terminal: false, cancelable: true, progress: 'active' },
  queued: { label: '已排队', terminal: false, cancelable: true, progress: 'active' },
  running: { label: '进行中', terminal: false, cancelable: true, progress: 'active' },
  success: { label: '执行结束', terminal: true, cancelable: false, progress: 'success' },
  failed: { label: '执行失败', terminal: true, cancelable: false, progress: 'exception' },
  cancelled: { label: '已取消', terminal: true, cancelable: false, progress: 'normal' }
}

/** 区分文件处理结果与任务执行状态，缺少记录时不产生成功数。 */
export function formatFileResultSummary(summary) {
  if (!summary || !summary.has_result || summary.total == null) return '文件结果待核对'
  if (summary.total === 0 && summary.has_result) return '本次没有处理文件'
  return `成功 ${summary.succeeded} · 失败 ${summary.failed} · 待处理 ${summary.pending} · 待核对 ${summary.unknown}`
}

/** 用文件状态而非操作按钮说明本次记录及当前结果。 */
export function fileResultStatusLabel(status) {
  const labels = {
    uploaded: '待解析',
    parsing: '解析中',
    parsed: '已解析',
    indexed: '已入库',
    done: '已入库',
    indexing: '入库中',
    error_parsing: '解析失败',
    error_indexing: '入库失败',
    failed: '处理失败',
    processing: '处理中',
    waiting: '等待中'
  }
  return labels[status] || '待核对'
}
