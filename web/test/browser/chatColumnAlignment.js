// 使用隔离 API fixture 验证聊天正文列与输入框居中关系；调用前页面需已打开应用。
// playwright-cli 将文件作为函数表达式执行，不能添加前导分号。
// prettier-ignore
async (page) => {
  const origin = new URL(page.url()).origin
  const agent = {
    id: 'qa-employee',
    slug: 'qa-employee',
    agent_id: 'qa-employee',
    name: '验收员工',
    can_manage: true,
    backend_id: 'chatbot',
    config_json: { context: { skills: [] } },
    configurable_items: { skills: { type: 'list', supports_all: true, default: [], options: [] } }
  }
  const thread = {
    id: 'qa-thread',
    agent_id: 'qa-employee',
    agent_slug: 'qa-employee',
    title: '布局验收',
    project_id: 'qa-project',
    metadata: {},
    thread_status: 'idle'
  }
  const body = Array.from(
    { length: 35 },
    (_, i) => `第${i + 1}项：用于验证宽屏正文可读宽度和人物间距。`
  ).join('\n\n')

  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let data = { data: [], items: [], models: [], providers: [], tasks: [], requests: [] }
    if (path === '/api/auth/me')
      data = { id: 99, uid: 'isolated-qa', username: '验收账号', role: 'superadmin' }
    else if (path === '/api/user/config') data = { default_agent_id: 'qa-employee' }
    else if (path === '/api/system/info')
      data = { success: true, data: { branding: { name: '布局验收' } } }
    else if (path === '/api/system/skill-navigation')
      data = { revision: 0, tree: [], configured: false }
    else if (path === '/api/system/health') data = { status: 'ok' }
    else if (path === '/api/agent') data = { agents: [agent] }
    else if (path === '/api/agent/qa-employee') data = { agent }
    else if (path === '/api/skills/accessible') data = { data: [] }
    else if (path === '/api/knowledge/databases/accessible' || path === '/api/knowledge/databases')
      data = { databases: [] }
    else if (path === '/api/chat/threads') data = [thread]
    else if (path === '/api/chat/projects' || path === '/api/projects')
      data = [
        { id: 'qa-project', name: '验收项目', status: 'active', selection_status: 'selectable' }
      ]
    else if (path === '/api/chat/thread/qa-thread/history')
      data = {
        thread,
        runs: [],
        history: [
          {
            id: 'human-1',
            type: 'human',
            content: '简短问题。',
            created_at: '2026-10-22T01:00:00Z'
          },
          { id: 'ai-short', type: 'ai', content: '简短回答。', created_at: '2026-10-22T01:00:10Z' },
          {
            id: 'human-2',
            type: 'human',
            content: '请详细说明。',
            created_at: '2026-10-22T01:00:20Z'
          },
          { id: 'ai-long', type: 'ai', content: body, created_at: '2026-10-22T01:00:30Z' }
        ]
      }
    else if (path === '/api/chat/thread/qa-thread' || path === '/api/chat/thread/qa-thread/viewed')
      data = thread
    else if (path.endsWith('/attachments')) data = { attachments: [] }
    else if (path.endsWith('/state')) data = { values: {}, files: {} }
    else if (path.endsWith('/audits')) data = { audits: [], truncated: false }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(data)
    })
  })

  await page.addInitScript(() => localStorage.setItem('user_token', 'isolated-browser-fixture'))
  const checks = []
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
    { width: 960, height: 900 },
    { width: 961, height: 900 },
    { width: 1024, height: 900 },
    { width: 1192, height: 900 },
    { width: 1193, height: 900 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto(`${origin}/chat/qa-thread`)
    await page.locator('.input-container').waitFor()
    await page.locator('.message-box.ai').nth(1).waitFor()
    await page.locator('.composer-mascot img').evaluate((img) => img.decode())
    await page.locator('.chat-box').evaluate((el) => {
      el.scrollTop = el.scrollHeight
    })
    const scrollCheck = await page.locator('.chat-box').evaluate(
      (el) =>
        new Promise((resolve) =>
          requestAnimationFrame(() => {
            const paragraphs = [...document.querySelectorAll('.message-box.ai .message-md p')]
            const lastParagraph = paragraphs.at(-1)
            const paragraphBottom = lastParagraph?.getBoundingClientRect().bottom ?? null
            const boxBottom = el.getBoundingClientRect().bottom
            resolve({
              scrollHeight: el.scrollHeight,
              clientHeight: el.clientHeight,
              scrollTop: el.scrollTop,
              scrollBottomDelta: el.scrollHeight - el.clientHeight - el.scrollTop,
              paragraphBottom,
              paragraphBottomGap: paragraphBottom === null ? null : boxBottom - paragraphBottom
            })
          })
        )
    )
    if (scrollCheck.scrollHeight <= scrollCheck.clientHeight) {
      throw new Error(`${viewport.width}px fixture 未产生可滚动消息列`)
    }
    if (Math.abs(scrollCheck.scrollBottomDelta) > 1) {
      throw new Error(`${viewport.width}px 消息列未滚动到底：差 ${scrollCheck.scrollBottomDelta}px`)
    }
    if (scrollCheck.paragraphBottom === null || scrollCheck.paragraphBottomGap < -1) {
      throw new Error(`${viewport.width}px 末条正文超出消息列：底部间距 ${scrollCheck.paragraphBottomGap}px`)
    }
    const measure = await page.evaluate(() => {
      const chatMain = document.querySelector('.chat-main').getBoundingClientRect()
      const box = document.querySelector('.chat-box').getBoundingClientRect()
      const input = document.querySelector('.input-container').getBoundingClientRect()
      const shell = document.querySelector('.composer-shell').getBoundingClientRect()
      const mascot = document.querySelector('.composer-mascot')
      const mascotRect = mascot?.getBoundingClientRect()
      const messages = [...document.querySelectorAll('.message-box.ai')].map((el) => {
        const r = el.getBoundingClientRect()
        return {
          centerX: (r.left + r.right) / 2,
          textLength: el.innerText.length,
          paragraphCount: el.querySelectorAll('.message-md p').length,
          centerDelta: (r.left + r.right) / 2 - (input.left + input.right) / 2,
          overlapsMascot: Boolean(
            mascotRect &&
            getComputedStyle(mascot).display !== 'none' &&
            mascotRect.left < r.right &&
            mascotRect.right > r.left &&
            mascotRect.top < r.bottom &&
            mascotRect.bottom > r.top
          )
        }
      })
      return {
        viewport: innerWidth,
        chatMainWidth: chatMain.width,
        chatColumnCenter: (box.left + box.right) / 2,
        inputCenter: (input.left + input.right) / 2,
        shellHeight: shell.height,
        inputHeight: input.height,
        mascotVisible: Boolean(mascot && getComputedStyle(mascot).display !== 'none'),
        mascotBottomToInputTop: mascotRect ? mascotRect.bottom - input.top : null,
        messages
      }
    })
    const delta = Math.abs(measure.chatColumnCenter - measure.inputCenter)
    if (delta > 1) throw new Error(`${viewport.width}px 消息列未居中：误差 ${delta}px`)
    if (measure.messages.length < 2) throw new Error('缺少短/长两条 AI 正文，无法验证遮挡')
    if (measure.messages[1].paragraphCount < 35) throw new Error('长正文未按真实段落渲染')
    if (measure.messages.some((message) => Math.abs(message.centerDelta) > 1)) {
      throw new Error(
        `${viewport.width}px 消息正文未居中：${measure.messages.map((message) => message.centerDelta).join(', ')}px`
      )
    }
    if (measure.messages.some((message) => message.overlapsMascot))
      throw new Error(`${viewport.width}px 人物遮挡了消息正文`)
    if (Math.abs(measure.shellHeight - measure.inputHeight) > 1)
      throw new Error(`${viewport.width}px composer 被人物增加了垂直占位`)
    if (measure.mascotVisible && Math.abs(measure.mascotBottomToInputTop) > 1)
      throw new Error(`${viewport.width}px 人物未贴合输入框上沿`)
    if (
      viewport.width >= 960 &&
      viewport.width <= 1193 &&
      measure.mascotVisible !== measure.chatMainWidth > 960
    ) {
      throw new Error(
        `${viewport.width}px 人物显示状态不符合 960px 容器阈值：容器 ${measure.chatMainWidth}px，显示 ${measure.mascotVisible}`
      )
    }
    checks.push({ ...measure, scrollCheck, centerDelta: delta })
  }
  await page.goto(`${origin}/chat`)
  await page.locator('.assistant-portrait').waitFor()
  await page.locator('.assistant-portrait img').evaluate((img) => img.decode())
  if (await page.locator('.composer-mascot').count())
    throw new Error('首页输入框重复显示了装饰人物')
  return { checks, homeHasNoComposerMascot: true }
}
