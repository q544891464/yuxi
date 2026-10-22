# basic 分支 Agent 交接

适用于接手 `basic` 开发、排障或开启新会话的 Agent。阅读前需要具备 Git 和 Docker Compose 基础；完成起步核查后，应能确认分支、保护已有工作、定位实际 Owner，并选择与任务风险匹配的验证。本页是内部交接操作指南，平台架构、开发约束和部署参数分别由原有文档维护。

## 先确认会话落点

在当前仓库根目录执行以下只读命令，确认分支为 `basic`，并记录已有修改；通过 worktree 列表定位其他分支的工作目录。

```bash
git branch --show-current
git status --short
git worktree list
git log -5 --oneline
git diff --stat
```

已有修改与未跟踪文件可能属于其他会话。先读取相关 diff；仅修改当前任务负责的文件，不使用 reset、clean 或覆盖复制清理工作树。涉及另一个分支时，在其已有 worktree 操作，先核对该目录的分支与状态。

随后读取 [AGENTS.md](AGENTS.md) 指定的架构、Spec Loop、工程信任、测试和贡献规范；修改对应子树时加载其 `AGENTS.md`。同时操作分支或运行环境时，先读[并行工作树与隔离运行环境](docs/develop-guides/parallel-worktree-environments.md)。

## 确认产品与分支边界

`basic` 是通用 Yuxi 数字员工平台，保留聊天、项目、附件、知识库、Skills、多智能体及管理能力。数字员工复用主 Agent 资料、运行配置和共享权限；`/employees` 打开员工广场，根路径按账号的有效默认员工进入对话，没有有效默认值时展示广场。普通聊天使用 `/chat`。产品范围见 [Basic 通用化决策](docs/develop-guides/decisions/implemented/2026-09-28-basic-edition.md)，入口与权限见[数字员工广场决策](docs/develop-guides/decisions/implemented/2026-10-21-basic-digital-employees.md)。

`cydx` 保留税务稽查、审理、督察角色、业务技能导航、行业人物与正式文书流转。Basic 已停用这些专属入口及默认注册；通用 Skills、知识库和解析能力继续保留。Basic 使用独立配置与数据环境，旧业务表、品牌或用户 Skill 的字节不由通用化代码自动删除。

两个分支都包含独有提交。同步时核对通用能力的 Owner、调用方、数据与测试，避免重新带入税务页面、业务角色和默认业务资源，也避免覆盖 Basic 的员工广场与账号默认配置。先比较提交来源和最终树：

```bash
git log --left-right --oneline basic...cydx
git diff --stat basic cydx
```

第一条命令显示双方独有提交，第二条显示两个分支最终树的差异；文件数不能证明功能已合并。是否同步、迁移或发布继续以当前任务授权为准。

## 按任务进入真实 Owner

先从[架构地图](ARCHITECTURE.md)定位领域，再沿入口、service、repository 和可观察结果追踪。下面只列本分支容易混淆的定位点；测试目录和执行方法由[测试规范](docs/develop-guides/testing-guidelines.md)维护。

| 任务 | 首要入口与职责 | 相关验证入口 |
|---|---|---|
| 员工广场与登录后入口 | [前端路由](web/src/router/index.js)、[员工广场](web/src/views/EmployeeSquareView.vue) 处理默认入口、员工选择与导航 | `web/test/unit/agentRouteSelection.test.js`、`basic_navigation.test.js` |
| 员工资料与能力配置 | [Agent 配置服务](backend/package/yuxi/services/agent_config_service.py)、[Agent repository](backend/package/yuxi/repositories/agent_repository.py) 拥有配置与可见性 | `backend/test/unit/services/test_agent_config_service.py`、`web/test/unit/agentConfigSave.test.js` |
| 账号默认员工 | [用户配置](backend/package/yuxi/config/user.py) 持久化 `default_agent_id`；有效性与 Schema 迁移边界见[广场决策](docs/develop-guides/decisions/implemented/2026-10-21-basic-digital-employees.md) | `backend/test/integration/api/test_user_config_api.py` |
| 员工聊天与侧栏 | [AgentView](web/src/views/AgentView.vue)、[AppLayout](web/src/layouts/AppLayout.vue)、[会话 Store](web/src/stores/chatThreads.js) 组合员工、历史和项目 | `web/test/unit/chatThreadsStore.test.js`、`projectConversationGroups.test.js` |

改动 Run、FIFO、SSE、恢复或文件边界时，回到架构中的完整主链路，并按测试规范执行真实链路验证。员工选择和技能菜单只投影可访问资源，后端授权继续拥有最终边界。

## 选择运行与交付环境

日常开发以 [docker-compose.yml](docker-compose.yml) 为准，生产服务组合以 [docker-compose.prod.yml](docker-compose.prod.yml) 为准。先确认当前工作树对应的 Compose project、状态目录和端口；只检查变量名与必要的非敏感值，不输出 `.env` 或展开后的完整配置。确认槽位归属后，使用服务名查看状态和日志：

```bash
docker compose ps
docker compose logs --tail=100 api worker storage-migrator
```

需要新环境或 Schema 不兼容时，按[隔离环境指南](docs/develop-guides/parallel-worktree-environments.md)建立独立槽位。Basic 与 cydx 使用独立配置和数据；初始化或迁移不能以覆盖另一分支状态的方式实现。

Basic 的 Linux ARM64 离线交付面向全新安装，部署入口是 [scripts/offline/README.md](scripts/offline/README.md)，同目录的打包、安装与验证脚本拥有实际行为。它加载预先准备的镜像、创建新状态和首位管理员，不迁移 cydx 账号或业务数据。目标端离线不等于模型内置，聊天、嵌入和重排模型仍需部署者提供可访问的服务。脚本逻辑检查为：

```bash
python3 -m unittest scripts.offline.test_offline
```

目标机安装、readiness 和断网工件验证按[ARM64 离线提案](docs/develop-guides/decisions/proposed/2026-10-22-basic-arm64-offline.md)验收，不能用脚本单测或 QEMU 检查替代原生硬件结果。

## 交接快照与待核对事项

快照日期：2026-10-23；首次任务验证基线：`fd1b19b6` 加对应实现。以下仅帮助定位接手工作，实时状态由 Git、对应提案和运行环境决定。提案文件如已移动，先在 `docs/develop-guides/decisions/` 搜索其主题并读取新状态。

| 工作 | 接手入口 | 核对时的边界 |
|---|---|---|
| 员工会话、技能范围与侧栏精简 | [侧栏决策](docs/develop-guides/decisions/implemented/2026-10-22-employee-chat-sidebar.md)；实现提交 `715ce2c5` | 已实现；快速切换、历史深链接、搜索归档、技能交集和成果预览的证据与未验证范围由该记录维护 |
| 知识库与技能管理导航 | [管理导航决策](docs/develop-guides/decisions/implemented/2026-10-22-management-navigation.md)；实现提交 `9dd2ceab` | 已拆分独立知识库入口，技能管理承接侧栏技能配置，重复工作台入口已移除；后续改动保留导航与权限回归 |
| 产品审查与首轮整改 | [产品审查](docs/develop-guides/basic-product-review.md)与[首轮执行计划](docs/develop-guides/decisions/proposed/2026-10-22-basic-product-first-round.md) | [统计与后台任务结果](docs/develop-guides/decisions/implemented/2026-10-22-dashboard-task-results.md)、[首次任务引导](docs/develop-guides/decisions/implemented/2026-10-22-first-task-guidance.md)已完成对应整改；下一包为创建配置与试运行，之后推进“我的工作”及目标用户试点 |
| ARM64 全新离线安装 | [离线提案](docs/develop-guides/decisions/proposed/2026-10-22-basic-arm64-offline.md)与[安装说明](scripts/offline/README.md) | 源码脚本已存在，提案整体仍为 proposed；目标 DGX Spark 原生安装与完整 readiness、断网验收仍需补齐 |
| 数字员工既有验证限制 | [广场决策的验证与后果](docs/develop-guides/decisions/implemented/2026-10-21-basic-digital-employees.md#后果) | 保留后端全量 unit 未完整通过及真实模型、检索、worker、沙盒链路未验证的记录；页面或定向测试结果不能扩展为全链路通过 |

接手产品整改时先核对基线之后的实现，已提交的侧栏、导航及工作包 1、2 只做回归；创建试运行与“我的工作”的详细范围以首轮提案为准。产品审查中的部署页面未逐一匹配 Git 版本，不能将其观察扩展为当前 HEAD 的全链路验收。

## 新会话起步与下一次交接

可把下面这段作为新会话的首条任务说明，并补齐具体目标：

```text
请接手当前项目的 basic 分支。先读 AGENTS.md 和 AGENT_HANDOFF.md，
按约定加载架构与开发规范，核对实际分支、HEAD、worktree 和已有修改。
本次目标：<用户可观察的结果与验收条件>。
先给出目标、非目标、假设和每步的验证方式，再定位源码 Owner。
保持通用数字员工定位与独立数据环境；保留其他会话的修改。
按任务核对首轮产品整改、既有导航和 ARM64 离线提案的实际进度与剩余验收。
完成后报告改动文件、实际执行的检查及未执行原因。
```

结束任务时交接实际分支和 HEAD、已改文件及其归属、已验证结果、剩余验收和下一步入口。只在产品边界、Owner 或后续行动变化时更新本页，并刷新快照日期；详细决定继续写入对应 decision，完整命令与结果按[贡献流程](docs/develop-guides/contributing.md)记录。所有“通过”都需要实际证据，文档链接和构建成功只证明文档可用。
