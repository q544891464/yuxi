# 数字员工会话隔离与侧栏信息精简

状态：implemented
类型：feature
Owner：web/src/layouts/AppLayout.vue

## 问题

消费端会话和技能导航需要表达当前数字员工范围，切换员工后不能继续展示其他员工的入口。聊天右侧的技术状态与独立文件入口增加阅读负担，管理入口和员工广场需要放在稳定、容易找到的位置。

## 决策

消费端以当前选中的数字员工限定会话与技能，没有选择时隐藏这两个列表。会话使用已有员工归属；技能取员工已保存启用配置与用户可访问技能的交集，再受现有导航配置约束。缺少技能字段时沿用 schema 默认值，显式空数组保持为空；个人技能的菜单展示也遵循员工选择，运行时个人技能契约保持原有规则。

消费端左侧将管理员管理入口、数字员工广场放在新建对话上方，其余日常入口留在下方。右侧状态只展示待办和成果物，成果物可以打开预览。管理工作台保留原有跨员工会话列表及技术调试能力。

### 实现方案

`AppLayout` 将当前员工范围交给 `chatThreads` Store，统一列表、分页和状态刷新参数；员工变化使旧请求失效，并清空旧范围的展示。搜索和归档复用已有 HTTP 接口的员工筛选。`AgentView` 的路由恢复等待员工 Store 初始化；并发调用共享同一轮初始化。未知历史线程通过已有授权历史接口确认员工归属，消费端同步目标范围后加载会话；路由变化后不再使用过期结果。员工选择与配置只在详情成功且请求仍为最新时一起生效。

`AccessibleSkillMenu` 将可访问技能与员工持久配置取交集，再装配现有导航树。`AgentChatComponent` 根据消费端路由元数据控制状态内容与文件入口，保留成果物预览。全部改动属于前端投影，后端继续拥有用户授权、会话归属与运行结果；数据结构、运行执行及默认员工策略不变。

## 替代方案

- 保留全局会话与技能列表：无法表达当前员工范围。
- 为每个员工建立独立数据或权限体系：已有会话归属和技能配置足以表达需求，新增机制会扩大迁移与运维成本。
- 移除全部文件预览：会妨碍用户阅读成果，保留成果入口更符合完成任务的需要。

## 后果

消费端切换员工时需要重新加载该员工的列表；配置加载期间隐藏技能，避免展示旧员工配置。历史链接仍可选择所属员工并恢复会话。前端筛选不新增授权能力；用户不能通过员工选择获得额外资源权限。发布只需要更新前端资产。

## 验证

- `python scripts/verify_engineering_contracts.py` 通过，检查相对链接与工程边界；`python3 -m unittest scripts.test_verify_engineering_contracts` 在 Linux 环境 62/62 通过。Windows 执行同一测试有一项符号链接权限错误。
- `pnpm run lint:check`、`pnpm run build` 和文档目录 `pnpm run build` 通过。
- 相关 unit 50 项通过，覆盖员工切换、慢旧响应、分页与刷新范围、配置失败保留原员工、默认技能与显式空列表、并发初始化、路由恢复和状态精简。入口为 `web/test/unit/agentConfigSave.test.js`、`agentStoreInitialization.test.js`、`agentRouteSelection.test.js`、`agentThreadAccess.test.js`、`chatThreadsStore.test.js`、`accessible_skill_menu.test.js`、`accessibleSkills.test.js`、`agentPanelSections.test.js`、`projectConversationGroups.test.js`，使用 `node --test` 执行。
- `npx --yes --package @playwright/cli playwright-cli --session fixture run-code --filename web/test/browser/employeeSidebar.js` 在生产构建预览通过。隔离 API fixture 的真实 DOM 证明 A/B 员工最近列表、搜索结果、归档抽屉与技能隔离、未选员工隐藏入口、普通用户无管理入口、冷启动历史深链恢复、仅技术字段时空态、待办与成果物及预览、浅深色、375/768/1024px 无横向溢出和移动导航。它不替代真实后端授权或运行恢复测试。
- 后端源码未修改；在无网络的独立容器内以只读源码与独立临时运行目录执行 `python -m pytest test/unit -m "not slow"`，2621 项通过。初次执行的临时技能目录不可写问题在修正容器目录后复验通过；不使用线上运行目录执行测试。
- 前端全量 unit 的一轮结果为 480/482：配置失败测试的 SSR 提示副作用已在测试中隔离，相关集合复验通过；知识库只读连接器的既有断言仍失败，其测试与涉及的两个页面源码均与原提交相同。该问题未计入通过，也未扩大本次修改范围。
- 本机无 Docker，仓库规定的 Compose 命令通过等价本地前端命令与隔离后端容器验证；真实模型执行、活动 Run 和队列恢复未验证。
