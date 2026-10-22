// 使用隔离 API fixture 验证消费端数字员工导航、技能与状态信息；调用前页面需已打开应用。
// playwright-cli 将文件作为函数表达式执行，不能添加前导分号。
// prettier-ignore
async (page) => {
  const origin = new URL(page.url()).origin
  const skills = [
    { slug: 'skill-alpha', name: 'A 专属技能', display_name: 'A 专属技能' },
    { slug: 'skill-beta', name: 'B 专属技能', display_name: 'B 专属技能' },
    { slug: 'skill-disabled', name: '员工未启用技能', display_name: '员工未启用技能', enabled: false }
  ]
  const employees = [
    {
      id: 'employee-a', slug: 'employee-a', name: '数字员工 A', backend_id: 'chatbot',
      config_json: { context: { skills: ['skill-alpha', 'skill-disabled', 'skill-private'] } },
      configurable_items: { skills: { type: 'list', supports_all: true, default: [], options: [] } }
    },
    {
      id: 'employee-b', slug: 'employee-b', name: '数字员工 B', backend_id: 'chatbot',
      config_json: { context: { skills: ['skill-beta'] } },
      configurable_items: { skills: { type: 'list', supports_all: true, default: [], options: [] } }
    }
  ]
  const threadA = {
    id: 'employee-a-thread', agent_id: 'employee-a', agent_slug: 'employee-a',
    title: 'A 员工会话', project_id: null, metadata: {}, thread_status: 'idle'
  }
  const threadB = {
    id: 'employee-b-thread', agent_id: 'employee-b', agent_slug: 'employee-b',
    title: 'B 员工会话', project_id: null, metadata: {}, thread_status: 'idle'
  }
  const archivedThreadA = { id: 'employee-a-archived', agent_id: 'employee-a', title: 'A 归档会话' }
  const archivedThreadB = { id: 'employee-b-archived', agent_id: 'employee-b', title: 'B 归档会话' }
  const threadState = {
    todos: [{ content: '整理客户资料', status: 'in_progress' }],
    artifacts: ['/outputs/交付方案.md'],
    token_usage: { llm_input_tokens: 1234, context_window: 8192 },
    files: { '/outputs/内部草稿.txt': { name: '内部草稿.txt' } },
    subagent_runs: [{ id: 'child-1', subagent_name: '后台研究员', status: 'completed' }]
  }
  const observedThreadScopes = []
  const observedHistoryPaths = []
  const observedSearchScopes = []
  const observedArchiveScopes = []
  let role = 'admin'
  let noEmployees = false
  let emptyState = false

  /** 通过员工广场选择指定员工并进入新对话。 */
  const chooseEmployee = async (employeeName) => {
    await page.locator('.consumer-top-nav').getByRole('link', { name: '数字员工广场' }).click()
    const employeeCard = page.locator('.employee-card').filter({ hasText: employeeName })
    await employeeCard.getByRole('button', { name: '开始对话' }).click()
    await page.locator('#consumer-sidebar').waitFor()
    const selectedSkill = employeeName === '数字员工 A' ? 'A 专属技能' : 'B 专属技能'
    await page.getByRole('button', { name: selectedSkill }).waitFor()
    await page.waitForURL((url) => url.pathname === '/chat' && !url.searchParams.has('agent_id'))
  }

  /** 按当前员工搜索对话并验证结果列表没有混入其他员工。 */
  const searchForEmployee = async (employeeId) => {
    const ownTitle = employeeId === 'employee-a' ? 'A 搜索结果会话' : 'B 搜索结果会话'
    const otherTitle = employeeId === 'employee-a' ? 'B 搜索结果会话' : 'A 搜索结果会话'
    await page.locator('.sidebar-search-trigger').click()
    const dialog = page.getByRole('dialog', { name: '搜索对话' })
    await dialog.getByRole('textbox', { name: '搜索对话' }).fill('隔离搜索')
    await dialog.getByText(ownTitle).waitFor()
    if (await dialog.getByText(otherTitle).count())
      throw new Error(`${employeeId} 搜索结果混入了其他员工会话`)
    await dialog.getByRole('button', { name: '关闭' }).click()
  }

  /** 打开归档抽屉并验证只显示当前员工会话。 */
  const verifyArchivedThreads = async (employeeId) => {
    const ownTitle = employeeId === 'employee-a' ? 'A 归档会话' : 'B 归档会话'
    const otherTitle = employeeId === 'employee-a' ? 'B 归档会话' : 'A 归档会话'
    await page.locator('.archive-entry').click()
    const drawer = page.locator('.archived-items-drawer')
    await drawer.getByText(ownTitle).waitFor()
    if (await drawer.getByText(otherTitle).count())
      throw new Error(`${employeeId} 归档抽屉混入了其他员工会话`)
    await page.locator('.ant-drawer-close').click()
  }

  /** 等导航与状态面板连续三帧保持同一位置后再截图。 */
  const waitForStableLayout = async () => {
    await page.evaluate(async () => {
      const readRects = () =>
        ['#consumer-sidebar', '.consumer-top-nav', '#agent-state-panel'].map((selector) => {
          const rect = document.querySelector(selector)?.getBoundingClientRect()
          return rect ? [rect.x, rect.y, rect.width, rect.height] : null
        })
      let previous = JSON.stringify(readRects())
      let stableFrames = 0
      for (let frame = 0; frame < 120 && stableFrames < 3; frame += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve))
        const current = JSON.stringify(readRects())
        stableFrames = current === previous ? stableFrames + 1 : 0
        previous = current
      }
      if (stableFrames < 3) throw new Error('导航或状态面板布局未稳定')
    })
  }

  await page.route('**/api/**', async (route) => {
    const requestUrl = new URL(route.request().url())
    const path = requestUrl.pathname
    if (path.includes('/api/chat/thread/') && path.endsWith('/history')) observedHistoryPaths.push(path)
    let data = { data: [], items: [], models: [], providers: [], tasks: [], requests: [] }
    if (path === '/api/auth/me')
      data = { id: 99, uid: 'employee-sidebar-fixture', username: '侧栏验收账号', role }
    else if (path === '/api/user/config') data = { default_agent_id: noEmployees ? null : 'employee-a' }
    else if (path === '/api/system/info')
      data = { success: true, data: { branding: { name: '员工侧栏验收' } } }
    else if (path === '/api/system/skill-navigation')
      data = { revision: 0, tree: [], configured: false }
    else if (path === '/api/system/health') data = { status: 'ok' }
    else if (path === '/api/agent/backends') data = { backends: [{ id: 'chatbot', name: 'Chatbot' }] }
    else if (path === '/api/agent') data = { agents: noEmployees ? [] : employees }
    else if (path === '/api/agent/employee-a' || path === '/api/agent/employee-b')
      data = { agent: employees.find((employee) => path.endsWith(employee.id)) }
    else if (path === '/api/tools' || path === '/api/agent/tools') data = { data: [] }
    else if (path === '/api/skills/accessible')
      data = { data: skills }
    else if (path === '/api/knowledge/databases/accessible' || path === '/api/knowledge/databases')
      data = { databases: [] }
    else if (path === '/api/chat/threads/search') {
      const agentId = requestUrl.searchParams.get('agent_id')
      if (agentId) observedSearchScopes.push(agentId)
      data = {
        items: agentId === 'employee-a'
          ? [{ id: 'employee-a-search', agent_id: agentId, title: 'A 搜索结果会话', snippets: [{ content: '隔离搜索 A 员工结果' }] }]
          : agentId === 'employee-b'
            ? [{ id: 'employee-b-search', agent_id: agentId, title: 'B 搜索结果会话', snippets: [{ content: '隔离搜索 B 员工结果' }] }]
            : [],
        has_more: false
      }
    } else if (path === '/api/chat/threads') {
      const agentId = requestUrl.searchParams.get('agent_id')
      if (agentId) observedThreadScopes.push(agentId)
      if (requestUrl.searchParams.get('status') === 'archived') {
        if (agentId) observedArchiveScopes.push(agentId)
        data = agentId === 'employee-a' ? [archivedThreadA] : agentId === 'employee-b' ? [archivedThreadB] : []
      } else {
        data = agentId === 'employee-a' ? [threadA] : agentId === 'employee-b' ? [threadB] : []
      }
    } else if (path === '/api/chat/projects' || path === '/api/projects') data = []
    else if (path === '/api/chat/thread/employee-a-thread/history')
      data = {
        thread: threadA,
        runs: [],
        history: [
          { id: 'human-a', type: 'human', content: '请准备交付方案。', created_at: '2026-10-22T01:00:00Z' },
          { id: 'assistant-a', type: 'ai', content: '交付方案已准备。', created_at: '2026-10-22T01:00:10Z' }
        ]
      }
    else if (path === '/api/chat/thread/employee-b-thread/history')
      data = {
        thread: threadB,
        runs: [],
        history: [
          { id: 'human-b', type: 'human', content: '请查看员工 B 的会话。', created_at: '2026-10-22T02:00:00Z' },
          { id: 'assistant-b', type: 'ai', content: 'B 员工的历史回复。', created_at: '2026-10-22T02:00:10Z' }
        ]
      }
    else if (path === '/api/chat/thread/employee-a-thread') data = threadA
    else if (path === '/api/chat/thread/employee-b-thread') data = threadB
    else if (path === '/api/chat/thread/employee-a-thread/state')
      data = { agent_state: threadState, interrupt: null }
    else if (path === '/api/chat/thread/employee-b-thread/state')
      data = {
        agent_state: emptyState
          ? { token_usage: threadState.token_usage, files: threadState.files, subagent_runs: threadState.subagent_runs }
          : { todos: [{ content: '完成员工 B 任务', status: 'completed' }], artifacts: [] },
        interrupt: null
      }
    else if (path.endsWith('/attachments')) data = { attachments: [] }
    else if (path.endsWith('/audits')) data = { audits: [], truncated: false }

    if (path.includes('/artifacts/')) {
      await route.fulfill({ status: 200, contentType: 'text/plain', body: '成果预览 fixture 内容' })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(data)
    })
  })

  await page.addInitScript(() => localStorage.setItem('user_token', 'isolated-employee-sidebar-fixture'))
  const checks = {}
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${origin}/chat`)
  await page.evaluate(() => localStorage.removeItem('agent-store'))
  await page.reload()
  await page.locator('#consumer-sidebar').waitFor()
  await page.getByRole('link', { name: '员工管理' }).waitFor()
  const navOrder = await page.evaluate(() => {
    const top = document.querySelector('.consumer-top-nav')
    const primary = document.querySelector('.consumer-primary-nav')
    return {
      topLabels: [...(top?.querySelectorAll('.nav-text') || [])].map((item) => item.textContent.trim()),
      topBeforeNewChat: Boolean(top && primary && top.compareDocumentPosition(primary) & Node.DOCUMENT_POSITION_FOLLOWING)
    }
  })
  if (!navOrder.topBeforeNewChat || !navOrder.topLabels.includes('数字员工广场'))
    throw new Error('管理员入口与数字员工广场没有排列在新建对话上方')
  checks.adminNavigation = navOrder

  const sidebar = page.locator('#consumer-sidebar')
  await page.getByRole('button', { name: 'A 专属技能' }).waitFor()
  if (await page.getByRole('button', { name: 'B 专属技能' }).count())
    throw new Error('员工 A 的技能菜单显示了员工 B 的技能')
  if (await page.getByRole('button', { name: '员工未启用技能' }).count())
    throw new Error('技能菜单显示了当前员工未启用的技能')
  if (await sidebar.getByText('无访问权限技能').count())
    throw new Error('技能菜单显示了 ACL 不可访问的技能')
  await sidebar.getByText('A 员工会话').waitFor()
  if (await sidebar.getByText('B 员工会话').count())
    throw new Error('员工 A 的会话列表显示了员工 B 的会话')
  checks.employeeA = { session: 'A 员工会话', skill: 'A 专属技能' }

  await chooseEmployee('数字员工 B')
  await page.getByRole('button', { name: 'B 专属技能' }).waitFor()
  await sidebar.getByText('B 员工会话').waitFor()
  if (await page.getByRole('button', { name: 'A 专属技能' }).count())
    throw new Error('切换到员工 B 后残留员工 A 的技能')
  if (await sidebar.getByText('A 员工会话').count())
    throw new Error('切换到员工 B 后残留员工 A 的会话')
  if (!observedThreadScopes.includes('employee-a') || !observedThreadScopes.includes('employee-b'))
    throw new Error(`会话列表没有分别按员工加载：${observedThreadScopes.join(', ')}`)
  checks.employeeB = { session: 'B 员工会话', skill: 'B 专属技能', threadScopes: observedThreadScopes }

  await searchForEmployee('employee-b')
  if (!observedSearchScopes.includes('employee-b'))
    throw new Error(`员工 B 搜索请求未按员工过滤：${observedSearchScopes.join(', ')}`)
  checks.employeeBSearch = { result: 'B 搜索结果会话', searchScopes: observedSearchScopes }
  await verifyArchivedThreads('employee-b')
  if (!observedArchiveScopes.includes('employee-b'))
    throw new Error(`员工 B 归档请求未按员工过滤：${observedArchiveScopes.join(', ')}`)
  checks.employeeBArchive = { result: 'B 归档会话', archiveScopes: observedArchiveScopes }

  await chooseEmployee('数字员工 A')
  await searchForEmployee('employee-a')
  if (!observedSearchScopes.includes('employee-a'))
    throw new Error(`员工 A 搜索请求未按员工过滤：${observedSearchScopes.join(', ')}`)
  checks.employeeASearch = { result: 'A 搜索结果会话', searchScopes: observedSearchScopes }
  await verifyArchivedThreads('employee-a')
  if (!observedArchiveScopes.includes('employee-a'))
    throw new Error(`员工 A 归档请求未按员工过滤：${observedArchiveScopes.join(', ')}`)
  checks.employeeAArchive = { result: 'A 归档会话', archiveScopes: observedArchiveScopes }
  await page.getByRole('button', { name: 'A 专属技能' }).waitFor()
  await page.waitForURL((url) => url.pathname === '/chat' && !url.searchParams.has('agent_id'))
  await page.goto(`${origin}/chat/employee-b-thread`)
  try {
    await page.getByText('B 员工的历史回复。').waitFor({ timeout: 8000 })
  } catch {
    throw new Error(`深链未加载 B 历史；url=${page.url()}，历史请求=${observedHistoryPaths.join(',')}`)
  }
  await sidebar.getByText('B 员工会话').waitFor()
  await page.getByRole('button', { name: 'B 专属技能' }).waitFor()
  if (await sidebar.getByText('A 员工会话').count())
    throw new Error('深链打开 B 会话后侧栏仍保留员工 A 会话')
  if (await page.getByRole('button', { name: 'A 专属技能' }).count())
    throw new Error('深链打开 B 会话后技能仍来自员工 A')
  checks.deepLink = { threadHistoryAndScopeFollowEmployeeB: true }

  role = 'user'
  await page.reload()
  await page.locator('#consumer-sidebar').waitFor()
  if (await page.locator('.consumer-top-nav').getByText('员工管理').count())
    throw new Error('普通用户看到了管理员入口')
  if (await page.locator('.consumer-top-nav').getByText('数字员工广场').count() !== 1)
    throw new Error('普通用户的数字员工广场入口缺失或重复')
  checks.regularUser = { adminEntryHidden: true, employeePlazaVisible: true }

  noEmployees = true
  role = 'admin'
  await page.goto(`${origin}/chat`)
  await page.evaluate(() => localStorage.removeItem('agent-store'))
  await page.reload()
  await page.locator('#consumer-sidebar').waitFor()
  if (await page.locator('.recent-history-group').count())
    throw new Error('未选择数字员工时仍显示最近会话区')
  if (await page.locator('.archive-entry').count())
    throw new Error('未选择数字员工时仍显示归档会话入口')
  if (await page.locator('.consumer-function-menu').getByRole('button', { name: '技能' }).count())
    throw new Error('未选择数字员工时仍显示技能入口')
  checks.noEmployee = { recentAndArchiveHidden: true, skillControlHidden: true }

  noEmployees = false
  emptyState = true
  await page.evaluate(() => localStorage.removeItem('agent-store'))
  await page.reload()
  await page.locator('#consumer-sidebar').waitFor()
  await chooseEmployee('数字员工 B')
  await page.locator('.conversation-select').filter({ hasText: 'B 员工会话' }).click()
  await page.locator('button[aria-controls="agent-state-panel"]').click()
  await page.locator('#agent-state-panel').getByText('当前没有待办或成果物').waitFor()
  checks.emptyState = { technicalDataDoesNotReplaceEmptyMessage: true }

  emptyState = false
  await page.goto(`${origin}/chat`)
  await chooseEmployee('数字员工 A')
  await page.locator('.conversation-select').filter({ hasText: 'A 员工会话' }).click()
  await page.locator('button[aria-controls="agent-state-panel"]').click()
  await page.getByText('整理客户资料').waitFor()
  await page.locator('#agent-state-panel .state-list-item--artifact').waitFor()
  const statePanel = page.locator('#agent-state-panel')
  for (const hiddenText of ['上下文占用', '附件/文件', '后台研究员', '子智能体']) {
    if (await statePanel.getByText(hiddenText, { exact: true }).count())
      throw new Error(`消费端状态面板仍显示技术信息：${hiddenText}`)
  }
  if (await page.locator('button[aria-controls="agent-file-panel"]').count())
    throw new Error('消费端仍显示独立文件入口')
  await waitForStableLayout()
  await page.screenshot({ path: 'output/playwright/employee-sidebar-desktop.png', fullPage: false })
  await page.evaluate(() => document.documentElement.classList.add('dark'))
  await page.screenshot({ path: 'output/playwright/employee-sidebar-desktop-dark.png', fullPage: false })
  await page.evaluate(() => document.documentElement.classList.remove('dark'))
  await page.locator('#agent-state-panel .state-list-item--artifact').click()
  await page.getByText('成果预览 fixture 内容').waitFor()
  await waitForStableLayout()
  await page.screenshot({ path: 'output/playwright/employee-sidebar-artifact-preview.png', fullPage: false })
  checks.consumerState = {
    todoVisible: true,
    artifactVisible: true,
    contextFilesSubagentsHidden: true,
    artifactPreviewOpened: true
  }

  const responsiveChecks = []
  for (const width of [375, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 })
    const dimensions = await page.evaluate(() => ({
      viewport: innerWidth,
      document: document.documentElement.scrollWidth,
      sidebar: document.querySelector('#consumer-sidebar')?.getBoundingClientRect().width || 0
    }))
    if (dimensions.document > dimensions.viewport + 1)
      throw new Error(`${width}px 页面出现横向溢出：${dimensions.document}px`)
    responsiveChecks.push(dimensions)
  }
  checks.responsive = responsiveChecks

  await page.goto(`${origin}/chat`)
  await page.reload()
  await page.locator('#consumer-sidebar').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '切换导航菜单' }).click()
  await page.locator('#consumer-sidebar').getByRole('link', { name: '员工管理' }).waitFor()
  await page.locator('#consumer-sidebar').getByRole('link', { name: '数字员工广场' }).waitFor()
  await waitForStableLayout()
  await page.screenshot({ path: 'output/playwright/employee-sidebar-mobile.png', fullPage: false })
  checks.mobileNavigation = { width: 390, adminAndPlazaVisible: true }
  return checks
}
