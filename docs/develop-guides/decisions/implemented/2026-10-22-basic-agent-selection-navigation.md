# Basic 异步员工选择不得覆盖离页导航

状态：implemented
类型：bug-fix
Owner：web/src/views/AgentView.vue

## 问题

聊天页通过 agent_id 选择员工时有异步初始化和线程切换。期间用户已进入数字员工广场、配置或知识库，旧任务的 finally 仍替换当前路由，导致页面被拉回聊天页。

## 决策

### 实现方案

以发起选择时的 Vue Router 当前路由对象作为本次操作的归属。在选择下一步、报错和移除 agent_id 前，确认路由仍是同一对象；进入别页、修改查询或离开后返回相同 URL 都使旧任务失效。仅聊天新会话路由消费员工选择，不改变权限、API、模型配置或业务数据。

## 替代方案

- 延迟启用导航会让用户等待网络且无法证明异步操作已结束。
- 停用 keep-alive 会改变会话缓存，也不能撤销已发出的 Promise。
- 仅检查 URL 字符串无法区分离开后返回同一地址。

## 后果

不取消已经发出的后端读取请求，也不改变 agentStore 已开始的请求语义；保护范围限于此页面拥有的后续交互和导航。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 过期员工选择不能改变用户新页面 | await 后继续执行选择或 finally 导航 | web/src/views/AgentView.vue | 可控延迟 unit 与真实浏览器 DOM/路由回读 | 原代码在离页后回到 /chat | Passed：修复前 6 项负例失败，修复后通过；延迟浏览器复现修复前回跳、修复后保留目标页面 |
| 当前聊天仍可选择员工并消费 agent_id | 保护条件误拦有效请求 | 同上 | unit 成功/失败、聊天和管理入口回归 | 保留项目参数，当前错误可见 | Passed：有效员工选择移除一次性参数并保留项目，当前错误可见 |


- `node --test test/unit/agentRouteSelection.test.js test/unit/basic_navigation.test.js test/unit/layout_startup.test.js test/unit/agent_character_config.test.js`：18 项通过。新增测试调用页面实际函数，使用真实 Vue Router memory history 和可控 Promise；修复前 7 项中 6 项因被带回 /chat、删除新页面参数或显示过期错误而失败。
- `pnpm run lint:check`、`pnpm run build`：通过。
- 真实 Chrome、本地 production build、全部 API 使用隔离 fixture：GET /api/agent/qa-employee 挂起时先进入广场或配置，回读 DOM 确认已显示，然后释放请求；修复前两例均 replaceState 到 /chat，修复后分别停留 /employees 和 /agent-manage。无延迟、直达广场两个对照不变；四例页面错误均为 0。修复前后各场景的路由时序和最终 DOM 截图已作为本次审查证据保留。
- `python scripts/verify_engineering_contracts.py`：通过。其 unittest 使用 D 盘临时目录执行 62 项，61 通过，1 项因 Windows 创建符号链接权限不足（WinError 1314）未通过；初次 C 盘临时目录还出现空间不足，转至隔离 D 盘目录后该环境问题消失。
- 本机无 Docker，所要求的后端 unit 命令无法执行；本次未改后端。`pnpm run test:unit` 共 470 项，468 通过、2 项既有失败（knowledge_detail_layout 旧返回链接断言、projectConversationGroups 旧空项目文案断言），均不在本次改动范围。
- `node node_modules/vitepress/bin/vitepress.js build`（docs 目录）通过，有现有大包警告；构建临时目录在完成后已自动清理。
- 全新、不继承开发上下文的 Reviewer 已审查功能、证据与完整改动；线上复核随前端部署完成记录。
