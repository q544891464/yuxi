# 回退首次任务引导

状态：implemented
类型：simplification
Owner：web/src/components/ChatWelcome.vue

## 问题

用户不接受 `e5e5b0c4` 的首次任务引导版本，要求从 `basic` 撤销该提交，同时保留 `fd1b19b6` 的满意度统计与任务结果展示修复。本文供后续维护者确认回退范围，前置知识为[首轮执行计划](../proposed/2026-10-22-basic-product-first-round.md)。

## 决策

### 实现方案

通过新提交完整反向应用 `e5e5b0c4`，前后端源码与测试恢复到 `fd1b19b6`。欢迎区、员工广场和草稿交互恢复该基线，员工配置服务与路由撤销 `starter_task_profile` 读投影；[满意度与后台任务结果](2026-10-22-dashboard-task-results.md)的服务、组件和测试完整保留。

首轮计划的工作包 2 标记为方案已撤销，后续重新确认设计再实施。本决定按用户指定提交执行完整回退，没有待裁决的新设计，直接记录为 implemented。范围仅为 `basic` 分支，不执行部署、数据库恢复或数据迁移。

## 替代方案

仅隐藏示例会遗留草稿交互与后端投影，也无法完整恢复用户认可的基线；直接重置分支会改写提交历史。采用完整 revert 保留历史和独立交付的工作包 1。

## 后果

欢迎页恢复员工形象、描述及账号资源统计，首次任务示例和预览填入能力撤销。已有会话、员工配置、草稿存储及任务结果不需要迁移。新用户引导的产品问题仍存在，工作包 2 需要重新设计。

## 验证

`git diff fd1b19b6 -- backend web` 为空，证明前后端与保留修复的基线一致。后端使用独立 Compose、完整仓库副本和合成数据；浏览器连接本地 Vite 与隔离 API。

| 证据 / 实际命令 | 结果 |
|---|---|
| `node --test web/test/unit/chatWelcome.test.js web/test/unit/digitalEmployees.test.js` | 8 passed |
| `cd web` 后执行 `pnpm run lint:check`、`pnpm run test:unit`、`pnpm run build` | 通过；490 tests passed |
| `docker compose --env-file verify.env -f rollback.verify.compose.json exec -T --user root -w /repo/backend api uv run --group test pytest test/unit -m 'not slow'` | 2633 passed、7 subtests passed、6 warnings |
| 同一 API 容器执行 `uv run --group test pytest test/unit/services/test_dashboard_service.py test/unit/services/test_task_result_service.py test/unit/services/test_agent_config_service.py -q` | 27 passed |
| 同一 API 容器执行 `uv run --group test pytest test/integration/api/test_dashboard_router.py test/integration/api/test_task_router.py -q` | 18 passed；真实 HTTP、PostgreSQL 及 worker 文件处理结果回读 |
| 真实 HTTP 读取员工列表与两个预置员工详情 | 响应不包含 `starter_task_profile`，两个预置员工仍可访问 |
| `playwright-cli run-code --filename web/test/browser/productResults.js` | 零样本与零分、部分失败、当前与历史状态、缺失及截断、分页、失败重试、迟到响应、空态、深浅主题与移动端通过 |
| 真实账号页面走查 | 原欢迎页、输入编辑、两个员工切换、示例与预览移除、375px 布局通过，无自动提交；真实满意度与任务页的当前/历史结果、刷新恢复及知识库跳转通过 |
| `python scripts/verify_engineering_contracts.py`、`python -m unittest scripts.test_verify_engineering_contracts` | 根契约通过；Linux 容器 62 tests passed |
| 修改的两个 Python 文件执行 `uv run --no-sync ruff check`、`uv run --no-sync ruff format --check`；`cd docs && pnpm run build`；`git diff --check` | 通过；前端及文档构建保留既有大 chunk 提示 |

欢迎页截图为 `output/playwright/rollback-welcome-light.png`、`rollback-welcome-dark.png`、`rollback-welcome-mobile.png`；真实任务页截图为 `output/playwright/product-results-live-detail.png`。日志与截图作为本地验收工件，不进入 Git。

浏览器初次运行受到并行单测的 Vite 缓存失效影响，前端单测完成并重启 Vite 后通过。隔离 API 的当前文件查询曾出现数据库连接池 `InterfaceError`，重启隔离 API 后完整页面复验通过。技能读取与技能导航仍观察到既有 500，本次不宣称完整技能链路通过；实际模型调用与业务试点为 `Not run`，回退不修改这些链路。

旧能力不存在：前后端源码中的首次任务示例、预览填入、专用草稿协调与 `starter_task_profile` 投影已删除，对应专用测试随提交撤销；欢迎区恢复基线的资源统计测试。

重新引入条件：产品重新确认首次任务引导设计及验收标准后，按首轮计划单独实施和验证。
