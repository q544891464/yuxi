// 隔离 API fixture 验证展示边界；真实 HTTP / PostgreSQL 由 integration 与单独页面走查覆盖。
// playwright-cli --session product-results run-code --filename web/test/browser/productResults.js
// prettier-ignore
async (page) => {
  await page.unroute('**/api/**')
  const origin = new URL(page.url()).origin
  const pageErrors = []
  const collectError = (error) => pageErrors.push(error.message)
  page.on('pageerror', collectError)
  let rate = null
  let detailError = false
  let currentError = false
  let noTasks = false
  let releaseDetail
  let delayed = false
  let detailReads = 0
  const date = '2026-10-22T08:00:00Z'
  const partial = {
    id: 'partial', name: '材料解析：部分失败', type: 'knowledge_parse', status: 'success',
    created_at: date, updated_at: date, completed_at: date, progress: 100,
    payload: { kb_id: 'qa-kb' },
    result: { items: [
      { file_id: 'qa-file', filename: '待处理材料.txt', status: 'error_parsing', error_message: '格式无法解析，请检查源文件。' },
      { filename: '操作说明.txt', status: 'parsed' }
    ] },
    file_result_summary: { total: 2, recorded: 2, succeeded: 1, failed: 1, pending: 0, unknown: 0, has_result: true, truncated: false }
  }
  const missing = { ...partial, id: 'missing', name: '已取消且没有结果', status: 'cancelled', result: null,
    file_result_summary: { total: null, recorded: 0, succeeded: 0, failed: 0, pending: 0, unknown: 0, has_result: false, truncated: false } }
  const truncated = { ...partial, id: 'truncated', name: '批量处理结果截断',
    result: { items: Array.from({length:200}, (_, i) => ({ filename: `材料${i + 1}.txt`, status: 'indexed' })) },
    file_result_summary: { total: 250, recorded: 200, succeeded: 200, failed: 0, pending: 0, unknown: 50, has_result: true, truncated: true } }
  const records = [partial, missing, truncated]
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let data = { data: [], items: [], agents: [], tasks: [], requests: [], models: [], providers: [] }
    let status = 200
    if (path === '/api/auth/me') data = { id: 99, uid: 'qa-results', username: '验收账号', role: 'admin' }
    else if (path === '/api/user/config') data = {}
    else if (path === '/api/system/skill-navigation') data = { revision: 1, configured: false, tree: [] }
    else if (path === '/api/system/info') data = { success: true, data: { branding: { name: '数字员工平台' } } }
    else if (path === '/api/chat/threads' || path === '/api/projects') data = []
    else if (path === '/api/dashboard/stats') data = { feedback_stats: { satisfaction_rate: rate, total_feedbacks: rate == null ? 0 : 2 } }
    else if (path === '/api/tasks') data = { tasks: noTasks ? [] : records.map((task) => { const summary = { ...task }; delete summary.payload; delete summary.result; return summary }), summary: { total: noTasks ? 0 : 3, status_counts: { success: 2, cancelled: 1 } } }
    else if (path.startsWith('/api/tasks/')) {
      detailReads++
      if (delayed) await new Promise((resolve) => { releaseDetail = resolve })
      status = detailError ? 503 : 200
      data = detailError ? { detail: '任务暂时无法读取，请重试。' } : { task: records.find((task) => task.id === path.split('/').at(-1)) }
    } else if (path.endsWith('/qa-file/basic')) data = currentError === 'missing' ? { status: 'failed', message: '文件不存在' } : { meta: { file_id: 'qa-file', filename: '待处理材料.txt', status: currentError === 'record' ? 'error_indexing' : 'indexed', error: currentError === 'record' ? '最近入库失败：合成错误原因' : null, updated_at: date } }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.addInitScript(() => { localStorage.setItem('user_token', 'isolated-results-fixture'); localStorage.setItem('theme', 'light'); localStorage.removeItem('agent-store') })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${origin}/dashboard`)
  const metric = page.locator('.stats-overview-container article').filter({ hasText: '满意度' })
  await metric.getByText('暂无评价', {exact:true}).waitFor()
  await metric.getByText('评价样本 0', {exact:true}).waitFor()
  rate = 0
  await page.reload()
  await metric.getByText('0%', {exact:true}).waitFor()
  await metric.getByText('评价样本 2', {exact:true}).waitFor()
  await page.screenshot({ path: 'output/playwright/product-results-zero.png', animations: 'disabled' })
  await page.getByRole('button', { name: '后台任务', exact: true }).first().click()
  const list = page.locator('.task-center-modal')
  const detail = page.locator('.task-detail')
  const closeDetail = () => detail.locator('..').locator('..').getByRole('button', {name:'Close',exact:true}).click()
  await list.getByText(partial.name, {exact:true}).click()
  await detail.getByText('成功 1 · 失败 1 · 待处理 0 · 待核对 0', {exact:true}).waitFor()
  if (!detailReads) throw new Error('详情未请求持久任务接口')
  await detail.getByRole('button', {name:'查看当前文件状态'}).click()
  await detail.getByText('待处理材料.txt · 已入库', {exact:true}).waitFor()
  await detail.getByText('格式无法解析，请检查源文件。', {exact:true}).waitFor()
  await page.screenshot({ path: 'output/playwright/product-results-light.png', animations: 'disabled' })
  currentError = 'record'
  await detail.getByRole('button', {name:'查看当前文件状态'}).click()
  await detail.getByText('最近入库失败：合成错误原因', {exact:true}).waitFor()
  await detail.getByText('格式无法解析，请检查源文件。', {exact:true}).waitFor()
  currentError = 'missing'
  await detail.getByRole('button', {name:'查看当前文件状态'}).click()
  await detail.getByText('无法读取文件当前状态，请返回知识库核对。', {exact:true}).waitFor()
  if (await detail.getByText('待处理材料.txt · 已入库', {exact:true}).count()) throw new Error('失败查询保留了过期当前状态')
  await detail.getByText('格式无法解析，请检查源文件。', {exact:true}).waitFor()
  await closeDetail()
  await list.getByText(truncated.name, {exact:true}).click()
  await detail.getByText('成功 200 · 失败 0 · 待处理 0 · 待核对 50', {exact:true}).waitFor()
  await detail.getByText('结果记录已截断，仅保留 200 项明细；其余结果待核对。', {exact:true}).waitFor()
  if (await detail.locator('.task-file-list li').count() !== 10) throw new Error('明细未分页')
  await detail.locator('.ant-pagination-item-2').click()
  await detail.getByText('材料11.txt', {exact:true}).waitFor()
  await closeDetail()
  await list.getByText(missing.name, {exact:true}).click()
  await detail.getByText('文件结果待核对', {exact:true}).waitFor()
  if (await detail.locator('.task-file-list li').count()) throw new Error('缺失结果伪造文件明细')
  await closeDetail()
  detailError = true
  await list.getByText(partial.name, {exact:true}).click()
  await detail.getByText('服务暂时无法完成操作，请稍后重试；若持续失败，请联系管理员。', {exact:true}).waitFor()
  detailError = false
  await detail.getByRole('button', {name:'刷新任务记录'}).click()
  await detail.getByText(partial.name, {exact:true}).waitFor()
  detailError = true
  await detail.getByRole('button', {name:'刷新任务记录'}).click()
  await detail.getByText('服务暂时无法完成操作，请稍后重试；若持续失败，请联系管理员。', {exact:true}).waitFor()
  await detail.getByText('格式无法解析，请检查源文件。', {exact:true}).waitFor()
  detailError = false
  await closeDetail()
  delayed = true
  await list.getByText(partial.name, {exact:true}).click()
  await detail.locator('.ant-spin-spinning').waitFor()
  await closeDetail()
  delayed = false
  await list.getByText(missing.name, {exact:true}).click()
  await detail.getByText(missing.name, {exact:true}).waitFor()
  const lateResponse = page.waitForResponse((response) => response.url().endsWith('/api/tasks/partial'))
  releaseDetail()
  await lateResponse
  await detail.getByText(missing.name, {exact:true}).waitFor()
  await closeDetail()
  await list.getByText(partial.name, {exact:true}).click()
  await detail.getByText(partial.name, {exact:true}).waitFor()
  await closeDetail()
  await list.getByRole('button', {name:'Close',exact:true}).click()
  await page.getByRole('button', {name:'切换主题',exact:true}).click()
  await page.getByRole('button', {name:'后台任务',exact:true}).first().click()
  await list.getByText(partial.name, {exact:true}).click()
  await detail.getByText(partial.name, {exact:true}).waitFor()
  await page.screenshot({ path: 'output/playwright/product-results-dark.png', animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'output/playwright/product-results-mobile.png', animations: 'disabled' })
  if (await detail.evaluate((element) => element.scrollWidth > element.clientWidth)) throw new Error('任务详情横向溢出')
  await closeDetail()
  noTasks = true
  await list.getByRole('button', {name:'刷新',exact:true}).click()
  await list.getByText('暂无任务', {exact:true}).waitFor()
  page.off('pageerror', collectError)
  if (pageErrors.length) throw new Error(pageErrors.join('; '))
  return { zeroAndNull:true, detailApi:true, historicalAndCurrent:true, missingAndTruncated:true, pagination:true, loadErrorAndRecovery:true, closedLateResponse:true, darkAndMobile:true, empty:true }
}
