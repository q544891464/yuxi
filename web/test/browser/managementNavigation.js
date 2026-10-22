// 隔离 API fixture 验证管理入口、详情返回及侧栏配置；调用前页面需已打开应用。
// playwright-cli 将文件作为函数表达式执行，不能添加前导分号。
// prettier-ignore
async (page) => {
  const origin = new URL(page.url()).origin
  let role = 'admin'
  let configError = false
  let conflict = false
  const skill = { slug: 'qa-skill', name: '资料整理', enabled: true, source_scope: 'shared' }
  const employee = {
    id: 'qa-employee', slug: 'qa-employee', name: '业务助手', backend_id: 'chatbot',
    config_json: { context: { skills: ['qa-skill'] } }, configurable_items: {}
  }
  const knowledge = { kb_id: 'qa-kb', name: '产品资料', description: '用于管理页面验收的示例资料。', kb_type: 'milvus', can_manage: true, files: {}, stats: { file_count: 0 } }
  let config = { revision: 1, configured: true, tree: [{ id: 'qa-entry', kind: 'entry', name: '资料整理入口', skillSlug: 'qa-skill', visibleRoles: ['admin', 'user', 'superadmin'], children: [] }] }
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let data = { success: true, data: [], items: [], tasks: [], models: [], providers: [], requests: [] }
    let status = 200
    if (path === '/api/auth/me') data = { id: 99, uid: 'management-fixture', username: '管理验收账号', role }
    else if (path === '/api/user/config') data = { default_agent_id: employee.id }
    else if (path === '/api/system/info') data = { success: true, data: { branding: { name: '数字员工平台' } } }
    else if (path === '/api/agent') data = { agents: [employee] }
    else if (path === '/api/agent/qa-employee') data = { agent: employee }
    else if (path === '/api/agent/backends') data = { backends: [{ id: 'chatbot', name: 'Chatbot' }] }
    else if (path === '/api/chat/threads' || path === '/api/chat/projects' || path === '/api/projects') data = []
    else if (path === '/api/skills/accessible' || path === '/api/skills') data = { data: [skill] }
    else if (path === '/api/system/skill-navigation/manage') {
      data = configError ? { detail: 'fixture unavailable' } : config
      status = configError ? 503 : 200
    } else if (path === '/api/system/skill-navigation') {
      if (route.request().method() === 'PUT') {
        if (conflict) { status = 409; data = { detail: 'fixture revision conflict' } }
        else { config = { ...route.request().postDataJSON(), configured: true, revision: config.revision + 1 }; data = config }
      } else data = config
    } else if (path === '/api/knowledge/databases' || path === '/api/knowledge/databases/accessible') data = { databases: [knowledge] }
    else if (path === '/api/knowledge/types') data = { kb_types: { milvus: { label: '本地知识库', supports_documents: true } } }
    else if (path === '/api/knowledge/databases/qa-kb') data = { ...knowledge, can_manage: role === 'admin' }
    else if (path === '/api/knowledge/databases/qa-readonly') data = { ...knowledge, kb_id: 'qa-readonly', supports_documents: false }
    else if (path.endsWith('/documents')) data = { items: [], total: 0, has_more: false }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.addInitScript(() => localStorage.setItem('user_token', 'isolated-management-fixture'))
  await page.evaluate(() => { localStorage.setItem('theme', 'light'); localStorage.removeItem('agent-store') })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${origin}/extensions`)
  await page.getByRole('heading', { name: '技能管理', exact: true }).waitFor()
  const tabs = page.getByRole('navigation', { name: '技能管理视图切换' })
  const tabNames = await tabs.getByRole('button').allTextContents()
  if (tabNames.map((name) => name.trim()).join(',') !== '技能,工具,MCP,侧栏技能') throw new Error('技能管理 Tab 不符合需求')
  if (await page.getByText('管理工作台', { exact: true }).count()) throw new Error('侧栏仍有工作台入口')
  await page.locator('.skill-cards-page').waitFor()
  await page.locator('.consumer-top-nav').getByRole('link', { name: '知识库管理', exact: true }).click()
  await page.getByRole('heading', { name: '知识库管理', exact: true }).waitFor()
  if (await page.locator('.database-container .tab-item').count()) throw new Error('知识库页仍有其他资源 Tab')
  await page.locator('.database-container').getByText('产品资料', { exact: true }).click()
  await page.waitForURL('**/knowledge/qa-kb')
  await page.getByRole('navigation', { name: '知识库详情导航' }).getByRole('button', { name: '知识库', exact: true }).click()
  await page.waitForURL('**/knowledge')
  await page.goto(`${origin}/extensions/knowledgebase/qa-kb`)
  await page.waitForURL('**/knowledge/qa-kb')
  await page.getByRole('navigation', { name: '知识库详情导航' }).waitFor()
  await page.goto(`${origin}/knowledge/qa-readonly`)
  await page.waitForURL('**/knowledge')
  await page.getByRole('heading', { name: '知识库管理', exact: true }).waitFor()
  await page.screenshot({ path: 'output/playwright/management-knowledge.png' })
  await page.locator('.consumer-top-nav').getByRole('link', { name: '技能管理', exact: true }).click()
  for (const [tab, panel] of [['工具', '.tools-cards-page'], ['MCP', '.mcp-cards-page']]) {
    await tabs.getByRole('button', { name: tab, exact: true }).click()
    await page.locator(panel).waitFor()
  }
  await tabs.getByRole('button', { name: '侧栏技能', exact: true }).click()
  const editor = page.locator('.navigation-settings')
  await editor.getByRole('textbox', { name: '技能中文显示名', exact: true }).fill('常用资料整理')
  conflict = true
  await editor.getByRole('button', { name: '保存配置', exact: true }).click()
  await editor.getByText('配置版本已被其他管理员更新。请重新加载最新配置后再保存。').waitFor()
  if (config.tree[0].name !== '资料整理入口') throw new Error('保存冲突覆盖了旧配置')
  conflict = false
  await editor.getByRole('button', { name: '保存配置', exact: true }).click()
  await page.locator('#consumer-sidebar').getByText('常用资料整理', { exact: true }).waitFor()
  await page.reload()
  await editor.getByRole('textbox', { name: '技能中文显示名', exact: true }).waitFor()
  await page.waitForFunction(() => [...document.querySelectorAll('.navigation-settings button')].some((button) => button.textContent.trim() === '重新加载' && !button.disabled))
  if (await editor.getByRole('textbox', { name: '技能中文显示名', exact: true }).inputValue() !== '常用资料整理') throw new Error('重新进入页面没有读取已保存配置')
  await page.screenshot({ path: 'output/playwright/management-sidebar-skills.png' })
  await page.locator('.user-info-dropdown').click()
  if (await page.getByText('管理工作台', { exact: true }).count()) throw new Error('用户菜单仍有工作台入口')
  await page.getByRole('menuitem', { name: '设置', exact: true }).click()
  await page.getByRole('button', { name: '关闭设置' }).waitFor()
  if (await page.locator('.settings-modal').getByText('侧栏技能', { exact: true }).count()) throw new Error('设置保留了重复侧栏技能入口')
  await page.getByRole('button', { name: '关闭设置' }).click()
  configError = true
  await page.reload()
  await editor.getByText('配置或技能列表加载失败，请重新加载。').waitFor()
  if (await editor.getByRole('button', { name: '保存配置', exact: true }).isEnabled()) throw new Error('未加载配置时允许保存')
  configError = false
  await page.reload()
  await editor.getByRole('textbox', { name: '技能中文显示名', exact: true }).waitFor()
  await page.locator('.user-info-dropdown').click()
  await page.getByRole('menuitem', { name: '切换到深色模式' }).click()
  await page.getByRole('heading', { name: '技能管理', exact: true }).click()
  await page.locator('.ant-dropdown:visible').waitFor({ state: 'hidden' })
  await page.screenshot({ path: 'output/playwright/management-sidebar-skills-dark.png', animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'output/playwright/management-mobile.png', animations: 'disabled' })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth || document.querySelector('.extensions-view').scrollWidth > document.querySelector('.extensions-view').clientWidth || [...document.querySelectorAll('.page-header .tab-item')].some((tab) => tab.getBoundingClientRect().right > innerWidth))
  if (overflow) throw new Error('手机页面横向溢出')
  role = 'user'
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${origin}/extensions?tab=navigation`)
  await page.locator('.skill-cards-page').waitFor()
  if ((await tabs.getByRole('button').allTextContents()).map((name) => name.trim()).join(',') !== '技能') throw new Error('普通用户看到了管理员 Tab')
  if (await page.locator('.navigation-settings').count()) throw new Error('普通用户挂载了共享配置')
  if (await page.locator('.consumer-top-nav').getByRole('link', { name: '知识库管理', exact: true }).count()) throw new Error('普通用户看到了知识库管理入口')
  await page.locator('.consumer-top-nav').getByRole('link', { name: '技能管理', exact: true }).waitFor()
  await page.goto(`${origin}/chat/knowledge/qa-kb`)
  await page.getByRole('navigation', { name: '知识库详情导航' }).getByRole('button', { name: '知识库', exact: true }).click()
  await page.waitForURL('**/chat/knowledge')
  await page.goto(`${origin}/extensions/knowledgebase/qa-kb`)
  await page.waitForURL('**/knowledge/qa-kb')
  await page.getByRole('navigation', { name: '知识库详情导航' }).getByRole('button', { name: '知识库', exact: true }).click()
  await page.waitForURL('**/chat/knowledge')
  await page.goto(`${origin}/knowledge/qa-readonly`)
  await page.waitForURL('**/chat/knowledge')
  return { splitPages: true, knowledgeDetailReturn: true, legacyLinks: true, readonlyRedirect: true, sidebarConfigSavedAndReloaded: true, conflictAndLoadError: true, noWorkbench: true, noDuplicateSettings: true, regularUserAccess: true, darkAndMobile: true }
}
