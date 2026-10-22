import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createServer } from 'vite'
import { formatFileResultSummary, fileResultStatusLabel } from '../../src/utils/taskResults.js'

test('缺少结果不能显示零失败或全成功，截断结果保留待核对数', () => {
  assert.equal(formatFileResultSummary(null), '文件结果待核对')
  assert.equal(formatFileResultSummary({ total: 0, has_result: false }), '文件结果待核对')
  assert.equal(formatFileResultSummary({ total: 0, has_result: true }), '本次没有处理文件')
  assert.equal(
    formatFileResultSummary({
      total: 250,
      has_result: true,
      succeeded: 198,
      failed: 2,
      pending: 0,
      unknown: 50
    }),
    '成功 198 · 失败 2 · 待处理 0 · 待核对 50'
  )
  assert.equal(fileResultStatusLabel('error_parsing'), '解析失败')
  assert.equal(fileResultStatusLabel('indexed'), '已入库')
  assert.equal(fileResultStatusLabel('parsed'), '已解析')
  assert.equal(fileResultStatusLabel('future'), '待核对')
})

test('满意度组件实际渲染区分无评价与 0%，并展示评价样本', async () => {
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  try {
    const { default: Component } = await server.ssrLoadModule(
      '/src/components/dashboard/StatsOverviewComponent.vue'
    )
    for (const [rate, count, label] of [
      [null, 0, '暂无评价'],
      [0, 2, '0%'],
      [66.67, 3, '66.67%']
    ]) {
      const html = await renderToString(
        createSSRApp({
          render: () =>
            h(Component, {
              basicStats: { feedback_stats: { satisfaction_rate: rate, total_feedbacks: count } }
            })
        })
      )
      assert.ok(html.includes(`>${label}</div>`), html)
      assert.ok(html.includes(`评价样本 ${count}`))
      if (rate == null) assert.ok(!html.includes('100%'))
    }
  } finally {
    await server.close()
  }
})
