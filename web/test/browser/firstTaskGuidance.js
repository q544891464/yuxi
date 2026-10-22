// 隔离响应覆盖首次任务交互；真实配置与权限由 HTTP integration 另行验证。
// prettier-ignore
async (page) => {
  await page.unroute('**/api/**')
  const origin = new URL(page.url()).origin
  const mutations = []
  const errors = []
  const collectError = (error) => errors.push(error.message)
  page.on('pageerror', collectError)
  const assistant = { id:'default-chatbot', slug:'default-chatbot', name:'智能助手', backend_id:'ChatbotAgent', starter_task_profile:'default-chatbot', config_json:{context:{}}, configurable_items:{system_prompt:{default:'You are a helpful assistant.'}} }
  const research = { id:'deep-research', slug:'deep-research', name:'深度研究', backend_id:'ChatbotAgent', starter_task_profile:'deep-research', config_json:{context:{skills:['deep-research'], subagents:['research-explorer','fact-verifier']}}, configurable_items:{skills:{options:[{key:'deep-research'}]}, subagents:{options:[{key:'research-explorer'},{key:'fact-verifier'}]}} }
  const custom = { ...assistant, id:'custom', slug:'custom', name:'同名智能助手', description:'只处理内部校对。', starter_task_profile:null }
  let employees = [assistant,research,custom]
  let listError = false
  const thread = { id:'qa-first-task', agent_id:'default-chatbot', title:'合成首次任务', project_id:'qa-project', metadata:{}, thread_status:'idle' }
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    let data = {data:[],items:[],models:[],providers:[],tasks:[],requests:[]}
    let status = 200
    if (request.method() === 'POST' && ['/api/chat/thread','/api/agent/runs'].includes(path)) mutations.push({path,body:request.postDataJSON()})
    if (path === '/api/auth/me') data = {id:99,uid:'first-task-fixture',username:'首次任务验收',role:'user'}
    else if (path === '/api/user/config') data = {default_agent_id:'deleted-default'}
    else if (path === '/api/system/info') data = {success:true,data:{branding:{name:'智能数字员工平台'}}}
    else if (path === '/api/system/skill-navigation') data = {revision:1,tree:[],configured:false}
    else if (path === '/api/agent') { data = {agents:employees}; status = listError ? 503 : 200 }
    else if (path === '/api/agent/backends') data = {backends:[]}
    else if (employees.some((agent) => path === `/api/agent/${agent.id}`)) {
      data = {agent:employees.find(agent => path.endsWith(`/${agent.id}`))}
    } else if (path === '/api/skills/accessible') data = {data:[{slug:'deep-research',name:'深度研究',enabled:true}]}
    else if (path.includes('/knowledge/databases')) data = {databases:[{kb_id:'unselected-kb',name:'账号可见但未启用资料',file_count:9999}]}
    else if (path === '/api/chat/threads' || path === '/api/projects') data = []
    else if (path === '/api/chat/thread' && request.method() === 'POST') data = thread
    else if (path === '/api/agent/runs') { status = 503; data = {detail:'合成发送失败'} }
    else if (path.endsWith('/history')) data = {thread,history:[],runs:[]}
    else if (path.endsWith('/state')) data = {agent_state:{},interrupt:null}
    else if (path.endsWith('/attachments')) data = {attachments:[]}
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)})
  })
  await page.addInitScript(() => { localStorage.setItem('user_token','first-task-fixture-token') })
  await page.evaluate(() => { localStorage.clear(); localStorage.setItem('user_token','first-task-fixture-token'); localStorage.setItem('theme','light') })
  await page.setViewportSize({width:1440,height:1000})
  await page.goto(`${origin}/employees`)
  await page.getByRole('heading',{name:'选择数字员工',exact:true}).waitFor()
  if (await page.getByRole('button',{name:'配置数字员工'}).count()) throw new Error('普通用户出现管理操作')
  const choose = async (slug) => {
    await page.goto(`${origin}/chat?agent_id=${slug}`)
    await page.waitForURL(url => url.pathname === '/chat' && !url.searchParams.has('agent_id'))
    await page.locator('.chat-welcome h1').getByText(employees.find(agent => agent.id === slug).name,{exact:true}).waitFor()
  }
  const input = page.locator('[contenteditable=true][role=textbox]')
  const dialog = page.getByRole('dialog',{name:'任务草稿预览'})
  const preview = title => page.locator('.starter-task').filter({hasText:title}).getByRole('button',{name:'预览示例'})
  await choose('default-chatbot')
  await preview('提炼材料要点').click()
  await dialog.getByText('[在这里粘贴材料]',{exact:false}).waitFor()
  if ((await input.innerText()).trim()) throw new Error('预览擅自修改草稿')
  await dialog.getByRole('button',{name:'填入草稿'}).click()
  if (!(await input.innerText()).includes('[在这里粘贴材料]')) throw new Error('未填入示例')
  await input.fill('需要保留的原稿')
  await preview('整理行动清单').click()
  await dialog.getByRole('button',{name:'保留原草稿'}).click()
  if (await input.innerText() !== '需要保留的原稿') throw new Error('原稿被覆盖')
  await preview('整理行动清单').click()
  await dialog.getByRole('button',{name:'替换当前草稿'}).click()
  const savedA = await input.innerText()
  await page.screenshot({path:'output/playwright/first-task-light.png',animations:'disabled'})
  await choose('deep-research')
  if ((await input.innerText()).trim()) throw new Error('A 草稿带入 B')
  await preview('对比两份材料').click()
  await dialog.getByRole('button',{name:'填入草稿'}).click()
  await input.fill('研究员工独立草稿')
  await choose('default-chatbot')
  if (await input.innerText() !== savedA) throw new Error('切回后 A 草稿丢失')
  await page.reload()
  await preview('提炼材料要点').waitFor()
  if (await input.innerText() !== savedA) throw new Error('刷新后草稿丢失')
  await preview('提炼材料要点').click()
  await page.goto(`${origin}/chat?agent_id=deep-research`)
  await page.waitForURL(url => url.pathname === '/chat' && !url.searchParams.has('agent_id'))
  if (await dialog.count()) throw new Error('切换员工仍保留旧确认')
  if (await input.innerText() !== '研究员工独立草稿') throw new Error('切换预览污染草稿')
  research.config_json.context.skills = []
  await page.reload()
  await page.getByText('研究所需的技能或协作员工未启用、不可访问或尚未加载。',{exact:false}).waitFor()
  if (await page.locator('.starter-task').count()) throw new Error('未启用技能仍出现示例')
  await choose('custom')
  await page.getByText('只处理内部校对。',{exact:true}).waitFor()
  if (await page.locator('.starter-task').count()) throw new Error('自建员工冒充预置')
  assistant.starter_task_profile = null
  await choose('default-chatbot')
  await page.getByText('该员工配置已调整或尚未核对',{exact:false}).waitFor()
  assistant.starter_task_profile = 'default-chatbot'
  await page.reload()
  await preview('提炼材料要点').waitFor()
  await page.locator('.user-info-dropdown').click()
  await page.getByRole('menuitem',{name:'切换到深色模式',exact:true}).click()
  await page.screenshot({path:'output/playwright/first-task-dark.png',animations:'disabled'})
  for (const width of [1024,768,375]) {
    await page.setViewportSize({width,height:1000})
    if (await page.locator('.chat-welcome').evaluate(el => el.scrollWidth > el.clientWidth)) throw new Error(`${width}px 欢迎区横向溢出`)
  }
  await page.screenshot({path:'output/playwright/first-task-mobile.png',animations:'disabled'})
  if (mutations.length) throw new Error('选择示例或编辑草稿自动创建了任务')
  await input.fill('合成会议记录：小王周五提交材料。')
  const sent = page.waitForResponse(response => response.url().endsWith('/api/agent/runs'))
  await page.locator('.send-button').click()
  await sent
  const submitted = mutations.find(item => item.path === '/api/agent/runs')?.body
  if (submitted?.agent_slug !== 'default-chatbot' || submitted?.query !== '合成会议记录：小王周五提交材料。') throw new Error('主动发送的员工或正文错误')
  employees = []
  await page.goto(`${origin}/employees`)
  await page.getByText('暂时没有可用的数字员工',{exact:true}).waitFor()
  listError = true
  await page.reload()
  await page.getByText('员工列表加载失败',{exact:true}).waitFor()
  listError = false
  employees = [assistant]
  await page.getByRole('button',{name:/重\s*试/}).click()
  await page.getByRole('heading',{name:'智能助手',exact:true}).waitFor()
  page.off('pageerror',collectError)
  if (errors.length) throw new Error(errors.join('; '))
  return {examples:true,draftPreserved:true,employeeIsolation:true,refreshPersistence:true,permissionAndConfigLimits:true,explicitSend:submitted,emptyAndError:true,responsive:true}
}
