# Basic 版合入上游并保持独立契约

状态：implemented
类型：architecture
Owner：backend/package/yuxi/services/agent_request_service.py

## 问题

Basic 版从较早的 Yuxi 主线分化；上游 `main` 截至 `8bfc2e88` 增加请求执行、模型重试、知识库、MCP、附件和前端多图片支持。直接沿用旧主线会错过通用修复；直接覆盖 Basic 则会失去通用品牌、对话恢复和已有权限行为。尤其 Basic 业务 Schema 已是 v10，上游新增 `model_providers.include_user_uid` 后，若不提升版本，现有 Basic 数据库会跳过新增列。

## 决策

### 实现方案

Basic 合入上游 `main`。`agent_request_service.py` 统一接收并持久化普通 Agent 请求，`agent_run_manifest_service.py` 在执行前从可见 Agent 配置构建 Context；Basic 保留已持久化 Context 的权限归一化。`AgentChatComponent.vue` 采用上游多图片输入契约，并保留 Basic 的发送失败核对与恢复。`storage_migration.py` 将业务 Schema 升至 v11，接受 v10 数据库并执行幂等的 `ensure_business_schema`；v10 已有文书表，不重复创建。Basic 路由与欢迎页继续提供通用入口，`cydx` 和线上环境不参与该决定。

Basic 的 System Tests 在合并后必须构建 Compose 的 `sandbox-runtime-image`，其默认镜像名仅存在本地，不能作为远程镜像执行 `docker pull`。合并后的后端单测 fixture 按可信持久配置与真实用户字段补齐，保持原有权限边界。

## 替代方案

- 只挑选少数修复：短期冲突少，但请求、前端与持久化契约相互依赖，容易漏改。
- 用上游覆盖 Basic：会恢复 Basic 已移除的产品入口，并丢失现有发送恢复行为。
- 不提升 Basic Schema 版本：已有 v10 数据库不会补齐上游新增列。

## 后果

合并保留上游通用能力与 Basic 的独立产品入口。现有 Basic v10 数据库需要在 Linux Compose 环境执行迁移后才能满足 v11 运行时预期；这次工作未对生产数据执行迁移。

## 验证

| 主张 | 语义 Owner | 证据 | 限制 |
|---|---|---|---|
| 上游更新与 Basic 修改并存 | Git ancestry、Basic 路由和产品文案 | 合并祖先检查、行业入口负向搜索 | 不涉及部署 |
| 发送失败恢复兼容多图片 | `AgentChatComponent.vue`、`AgentInputArea.vue` | 前端构建、相关单测和两图恢复负向案例通过 | 未在真实后端跑浏览器发送链路 |
| v10 数据库可升级至 v11 | `storage_migration.py`、`PostgresManager` | v10 迁移单测与 PostgreSQL 集成案例已写入 | 本地无 Docker，真实 PostgreSQL 测试尚未执行 |
| 通用运行链保持授权和结果绑定 | Agent request、manifest、repository | 工程契约、Ruff 和静态检查通过 | 本机 Windows 缺少 POSIX 文件 API，后端测试未形成有效通过证据 |

Linux Compose 的 backend unit、integration、E2E 尚未执行，v10→v11、Agent 请求 FIFO、附件和权限隔离仍缺少真实运行链证据。
