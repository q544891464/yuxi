# Basic 配置页面保持前台布局

状态：implemented
类型：bug-fix
Owner：web/src/router/index.js

## 问题

数字员工广场的配置入口、员工配置中的扩展入口、个人技能详情及搜索文件结果会导航到没有消费端布局标记的页面，导致同一操作流程的左侧栏突然切换。用户要求仅主动进入管理工作台时使用后台界面。

## 决策

### 实现方案

路由层为员工管理、扩展管理及其详情、文件工作区和独立总览统一声明消费端布局。AppLayout 继续使用既有 route.meta.consumerChat 选择外壳，不新增全局布局状态、持久配置或重复页面。/agent 及其线程路由保留管理员工作台外壳；进入这些路由的普通业务按钮按当前页面选择聊天入口，用户菜单的“管理工作台”保留显式跳转。

复用既有编辑器、知识库/技能授权、加载与错误处理。目标是保留前台导航，不改变资源权限、保存接口、模型输入、后端运行或用户数据。假设这些配置页面在直接访问和刷新后也使用相同前台布局，工作台中的管理入口导航到同一配置页面。

## 替代方案

- 为每一项功能复制消费端路由和管理视图会重复维护相同内容与链接。
- 用上一个页面或本地存储推断布局会让刷新和深链接的外壳不稳定。
- 只修改员工配置按钮会遗漏该页面内的扩展入口、个人技能及文件搜索。

## 后果

复用的配置内容需要在消费端可用区域内滚动，窄屏不能挤出左侧栏。既有后台直达书签仍有效，但配置页统一显示前台外壳。无需数据库迁移。

## 验证


| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 前台配置、扩展详情、工作区和总览保留侧栏 | 入口或子页面缺少布局标记 | web/src/router/index.js | basic_navigation.test.js 与真实浏览器跳转、刷新 | 移除布局标记后断言失败 | Pass：移除标记时新用例在 /agent-manage 失败；修复后路由和浏览器通过 |
| 从业务页面打开对话保持前台 | 仍硬编码管理员对话路由 | 业务页面导航处理函数 | 真实浏览器点击与路由回读 | 旧处理函数进入 /agent | Pass：员工去对话及定时任务打开对话均进入 /chat |
| 仅显式工作台使用后台外壳，权限不变 | 将布局当作授权或误改守卫 | router 与 UserInfoComponent | 普通用户拒绝管理页、管理员工作台浏览器检查 | 普通用户访问 /agent 仍被拒绝 | Pass：工作台显式切换；普通用户路由拒绝和配置入口隐藏通过 |



- `node --test test/unit/basic_navigation.test.js test/unit/layout_startup.test.js test/unit/agent_character_config.test.js test/unit/scheduledAgentAutosave.test.js`：21 项通过。新增路由用例在修复前因 /agent-manage 缺少消费端标记失败，修复后通过。
- `pnpm run lint:check`、`pnpm run build`：通过。
- Chrome 真实 DOM 验证（本地生产构建，API 使用隔离 fixture）：广场点击配置后侧栏 DOM 是同一节点、技能折叠状态不变；打开员工编辑、去对话、知识库管理、刷新、定时任务记录打开对话、技能详情返回均保留前台；管理员显式进入 /agent 切换后台，普通用户 /agent 被拒绝。1280×720、1920×1080、1024×768、768×1024、375×812 无水平溢出，页面错误 0。证据脚本与截图保存在本地 output/employee-verification/config-layout*.cjs 和 output/playwright/config-layout*.png。
- `pnpm run test:unit`：463 项，461 通过，2 项既有失败（knowledge_detail_layout 的旧返回链接断言、projectConversationGroups 的旧空项目文案断言）；对应实现及测试不在本次改动中。
- `python scripts/verify_engineering_contracts.py`、`git diff --check`：通过；`python -m unittest scripts.test_verify_engineering_contracts`：61 项通过，1 项因 Windows 无创建符号链接权限（WinError 1314）无法执行。
- `docker compose exec api uv run --group test pytest test/unit -m "not slow"`：本机无 Docker，未执行；本次没有后端改动。
- `node node_modules/vitepress/bin/vitepress.js build`（docs 目录）：通过，有现有大包警告。
- 全新且不继承实现上下文的 Reviewer `/root/consumer_shell_review` 审查需求、完整 diff、规范与证据，无阻断问题；app3 测试环境发布另以部署记录为准，不把 fixture 页面验证当作真实后端配置保存验证。
