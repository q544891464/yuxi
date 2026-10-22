import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createServer } from 'vite'
import { Button } from 'ant-design-vue'
import { RouterLink } from 'vue-router'
import { getEmployeeTaskGuide } from '../../src/utils/employeeTaskGuidance.js'

test('欢迎页以员工用途、材料和结果引导首次任务，不把账号资源数量当作能力', async () => {
  const server = await createServer({
    server: { middlewareMode: true, hmr: false },
    appType: 'custom'
  })
  try {
    const { default: Component } = await server.ssrLoadModule('/src/components/ChatWelcome.vue')
    const agent = {
      slug: 'default-chatbot',
      name: '智能助手',
      starter_task_profile: 'default-chatbot',
      config_json: { context: {} }
    }
    const guide = getEmployeeTaskGuide(agent, {}, {})
    /** 装配真实按钮后读取欢迎区渲染结果。 */
    const renderWelcome = (props) => {
      const app = createSSRApp({ render: () => h(Component, props) })
      app.component('a-button', Button)
      app.component('router-link', RouterLink)
      return renderToString(app)
    }
    const html = await renderWelcome({ agent, guide })
    for (const text of [
      '智能助手',
      '准备材料',
      '预期结果',
      '提炼材料要点',
      '整理行动清单',
      '预览示例',
      '检查后点击发送'
    ])
      assert.ok(html.includes(text), text)
    assert.ok(!html.includes('resource-stats'))
    assert.ok(!html.includes('Skills'))
    const loading = await renderWelcome({ agent, guide, loading: true })
    assert.ok(loading.includes('正在核对员工配置'))
    assert.ok(!loading.includes('预览示例'))
  } finally {
    await server.close()
  }
})
