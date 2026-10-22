# 满意度无样本与后台任务结果展示

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/repositories/dashboard_repository.py

## 问题

[首轮产品整改](../proposed/2026-10-22-basic-product-first-round.md)的第一个工作包处理统计与结果可信度。审查基线中，零反馈的整体及员工满意度返回 100；任务详情直接读取不含完整结果的列表缓存，文件部分失败、结果截断和后续重试缺少可核对的表达。本文面向维护统计和后台任务的开发者、测试人员，记录这一工作包的决定；其余工作包继续由原提案维护。

## 决策

### 实现方案

Dashboard repository 在零反馈时返回 `null`，统计组件同时展示“暂无评价”与样本量；全部差评保持 `0%`。整体和员工统计沿用同一可见会话及反馈范围，比例仍为好评数除以有效反馈数。

Task service 从 PostgreSQL Task 的结果生成 `file_result_summary`，只对知识导入、解析、入库任务统计明细；列表继续省略完整 payload/result。摘要由文件状态和错误证明，记录之外的数量保留为待核对，不使用 `processed - failed` 推算成功数。已解析文件只满足解析任务，入库任务仍需已入库状态。缺失及截断记录不显示全部成功。

入口统一称为“后台任务”，`success` 的展示文案为“执行结束”。TaskDetailModal 按需请求任务详情，提供分页文件明细、错误原因、刷新与返回知识库入口；原始 payload/result 收入技术详情。当前文件状态按用户操作调用既有 basic 接口，显示更新时间并与历史记录分开。读取失败保留历史，切换任务、刷新、关闭或退出账号后丢弃过期响应。HTTP 路由、任务状态机、文件写入和后端授权继续由原有模块负责。

## 替代方案

只改“已完成”的文案无法展示具体失败项；增加新的业务状态或执行引擎超出需求。采用已有 Task 结果的只读摘要与既有文件查询，保持管理员任务接口和知识资源权限边界。

## 验证

验证基线为 `basic@9a343e1c` 加本修复。后端使用独立 Compose project、全新 PostgreSQL/Redis/对象数据和合成账号；复用可用的 API 镜像运行本分支源码及测试依赖，全量 unit 从容器内的完整仓库副本执行。API 仅绑定回环地址，通过 SSH 转发连接本地 Vite 页面。前端在 Windows 使用已有锁定依赖验证。

| 证据 | 实际结果 |
|---|---|
| `pytest test/unit/services/test_dashboard_service.py test/unit/services/test_task_result_service.py -q` | 21 passed；无评价、全差评、混合评价、部分失败、无记录、未知状态、截断、解析与入库语义均覆盖 |
| 在旧默认值上运行 `test_dashboard_service.py -k satisfaction` | 4 failed；失败原因是无评价返回 100 而非 `None`，整体与员工均能捕获回归 |
| `pytest test/integration/api/test_dashboard_router.py test/integration/api/test_task_router.py -q` | 18 passed；真实 HTTP、反馈行、Task 和 KnowledgeFile 回读。覆盖历史失败且当前已入库、普通用户 403、文件删除后的失败响应；包括既有上传 → worker 解析 → 文件元数据链路 |
| `docker compose --env-file verify.env -f verify.compose.json exec -T --user root -w /repo/backend api uv run --group test pytest test/unit -m 'not slow'` | 2633 passed、7 subtests passed、6 warnings，无失败或跳过 |
| `pnpm run lint:check`、`pnpm run test:unit`、`pnpm run build` | 通过；前端全量 490 tests passed；最终组件、状态文案及刷新失败保留历史的定向用例 3 tests passed；构建保留既有大 chunk 提示 |
| 真实页面与隔离 HTTP | 无评价及样本 0、部分失败明细、当前状态与历史分开、刷新重开与返回知识库通过；截图 `output/playwright/product-results-live-dashboard.png`、`product-results-live-detail.png` |
| `playwright-cli run-code --filename web/test/browser/productResults.js` | fixture 覆盖 0%、无评价、分页截断、无记录、当前文件错误原因、加载错误与恢复、刷新失败保留历史、关闭后晚到响应、空列表、1440px 与 390px、真实主题切换；无未处理页面错误。截图前缀 `output/playwright/product-results-` 的 `zero/light/dark/mobile.png` |
| `python scripts/verify_engineering_contracts.py` 与 `python -m unittest scripts.test_verify_engineering_contracts` | 契约检查通过；62 tests 在 Linux 通过。Windows 单测受符号链接权限限制，保留实际失败记录 |
| `uv run ruff check package` 与改动 Python 源码的 `ruff format --check` | 通过；全量 package 格式检查存在 3 个未改文件的基线差异：conversation_repository、subagent_thread_repository、models_business |
| `cd docs && pnpm run build` 与 `git diff --check` | 文档、相对链接构建和差异空白检查通过 |

上述验证使用合成业务数据；截图和原始日志属于本地验收工件，不进入 Git。完整运行命令由[测试规范](../../testing-guidelines.md)维护。

## 后果

满意度 `null` 是公开响应语义变化，已同步当前统计组件；外部调用方需要区分空值与零。历史任务缺少文件 ID 或完整结果时只能返回知识库人工核对，旧数据无需迁移。一次详情请求不为全部文件加载当前状态；用户按需核对单个文件。图谱和评估任务继续通过技术详情展示原始结果。

隔离环境的技能目录读取有独立的 500 错误，本记录不将统计与任务验收扩展为技能、真实模型、检索或完整员工工作流通过。其余首轮工作包及目标用户可用性试验仍为 `Not run`。回退只涉及读模型及页面，不修改持久任务、文件处理或权限数据。
