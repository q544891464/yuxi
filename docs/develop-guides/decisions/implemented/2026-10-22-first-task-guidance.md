# 数字员工首次任务引导

状态：implemented
类型：feature
Owner：web/src/components/ChatWelcome.vue

## 问题

[首轮执行计划](../proposed/2026-10-22-basic-product-first-round.md)的第二个工作包面向首次使用数字员工的普通用户。审查基线的欢迎页突出账号资源数量，未说明如何准备材料和获得什么结果；预置员工可以被修改，按名称展示固定示例会误述能力。目标是让用户选到合适员工、预览示例并编辑当前员工草稿，最后明确发送。本文供产品、开发和测试人员审阅，需要了解既有员工配置、资源权限和本地草稿范围。

本包覆盖智能助手和深度研究，每个提供两个基于粘贴文本的示例。假设用户先完成平台模型配置；引导不证明模型连通性或回答质量。非目标为模板市场、自动发消息、文件生成承诺、创建试运行和“我的工作”。运行队列、后端授权与持久业务状态沿用既有实现。

## 决策

### 实现方案

员工配置服务参照仓库预置定义及默认配置，给既有员工响应增加只读的 `starter_task_profile`；名称相同的自建员工、角色或行为配置被修改的员工不匹配。模型和资源选择允许按部署配置变化，所需资源在前端依据员工配置与后端提供的当前用户可访问选项取交集。深度研究示例要求研究技能及研究、核查子员工可用，未知状态不推定可用。HTTP 路由只装配该读模型，不增加数据库字段或新接口。

员工广场展示用途和开始任务的说明；欢迎页以示例、材料、预期交付与三步操作提示取代账号资源数量。`employeeTaskGuidance.js` 拥有示例文本及筛选逻辑。智能助手示例为材料要点和行动清单，深度研究示例为研究计划和双材料对比；自建员工保留原描述和通用提示，依赖缺失或配置变化给出限制原因。

点击示例先预览完整草稿，已有输入时明确提供保留或替换。`useStarterTaskDraft` 在确认时核对上下文，仅写入 `AgentChatComponent` 当前用户、员工、项目范围的草稿，沿用原有浏览器草稿保存。线程、员工、项目、账号、路由、输入或示例适用性变化立即关闭预览。用户通过原输入框编辑和发送；填入草稿不创建线程、不发出 Run 请求。资源授权与运行结果继续由现有后端负责。

## 替代方案

按名称固定展示示例无法识别自建同名员工或被修改的角色；在前端复制预置提示词会形成第二份配置事实。采用后端只读匹配标识与既有权限选项。自动填写后发送容易误交付和覆盖草稿，采用先预览再确认。资源数量不帮助首次任务选择，因此移出欢迎页，资源访问仍沿用已有侧栏。

## 验证

验证基线为 `basic@fd1b19b6` 加本实现。后端复用上一工作包的独立 Compose 与合成数据槽位，加载当前分支源码；完整后端 unit 在容器内完整仓库副本执行。本地 Vite 经 SSH 转发连接回环 API，普通账号走查不拦截 HTTP。浏览器 fixture 单独覆盖负向状态，前端使用锁定依赖。

| 证据 | 实际结果 |
|---|---|
| `pytest test/unit/services/test_starter_task_profile.py test/unit/services/test_agent_config_service.py -q` | 15 passed；预置定义、同名自建、缺失或改写角色、行为配置变更均有结果断言 |
| `pytest test/integration/api/test_starter_task_guidance.py -q` | 3 passed；普通账号读取列表与详情，改写角色后撤回标识，回读 PostgreSQL 配置确认读取无副作用；私有同名员工保持跨用户不可见 |
| `docker compose --env-file verify.env -f verify.compose.json exec -T --user root -w /repo/backend api uv run --group test pytest test/unit -m 'not slow'` | 2642 passed、7 subtests passed、6 warnings，无失败或跳过 |
| `pnpm run lint:check`、`pnpm run test:unit`、`pnpm run build` | 通过；490 tests passed；构建保留既有大 chunk 提示。组件渲染、资源交集及草稿的定向集合 17 passed |
| `playwright-cli run-code --filename web/test/browser/firstTaskGuidance.js` | 覆盖两类员工示例、预览与保留/替换、配置及权限限制、员工切换与刷新、空态与失败重试、无效默认员工、普通用户管理入口、1440/1024/768/375px 和深浅主题。只有主动发送才提交 Run，核对正文及员工标识；Run 503 与列表 503 是预期负向响应，无未处理页面错误 |
| 真实普通账号页面与 PostgreSQL 回读 | 两类员工均可预览、填入和编辑，保留原稿、跨员工隔离、刷新恢复通过；未点击发送期间请求记录无创建动作，数据库会话、请求和 Run 均为 0。截图 `output/playwright/first-task-live-assistant.png`、`first-task-live-research.png` |
| `python scripts/verify_engineering_contracts.py`、`python -m unittest scripts.test_verify_engineering_contracts` | 根契约检查通过；Linux 容器 62 tests passed |
| 改动 Python 源码的 `uv run ruff check` 与 `uv run ruff format --check` | 通过 |
| `cd docs && pnpm run build`、`git diff --check` | 文档、相对链接构建与空白检查通过；文档构建保留既有大 chunk 提示 |

fixture 截图为 `output/playwright/first-task-light.png`、`first-task-dark.png`、`first-task-mobile.png`；日志与截图仅作为本地验收工件，不进入 Git。实际模型回答、检索和目标用户试点为 `Not run`；发送 fixture 只证明用户明确触发及出站协议，未证明真实模型执行成功。

示例的产品及业务负责人审核为 `Not run`，尚无目标部门确认的任务样本与交付标准。该审核归入整体首轮计划的目标用户试点，由产品与业务负责人确认材料、预期结果及模型实际输出。代码与交互验收完成只表示引导可用，不代表示例的业务验收通过。

## 后果

示例配置标识只用于展示，调用授权和模型就绪仍由原后端检查。角色配置变化时保守隐藏示例，管理员可核对配置，普通用户可按现有描述自行输入。草稿继续使用浏览器存储，沿用既有跨设备限制。验证使用独立 Compose 与合成数据，不修改生产账号和员工配置；回退无需数据迁移。

真实普通账号走查中，隔离环境的 `/api/skills/accessible` 仍返回既有的 500，侧栏显示技能加载失败；员工详情提供的可访问配置选项及本包草稿操作可用。该错误由环境与技能读取链路后续排查，本包不宣称完整技能、模型或员工工作流通过。创建试运行、“我的工作”和目标用户试点继续由整体首轮计划维护。
