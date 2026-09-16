# 个人技能 ZIP 导出

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/service.py

## 问题

共享技能已有管理导出接口，个人技能仅支持预览和卸载，用户无法下载完整技能目录。

## 决策

为当前登录用户添加个人技能 ZIP 导出接口，在个人技能预览弹窗提供导出按钮。包内以技能 slug 为根目录，保留 SKILL.md、脚本、资源、二进制文件和空目录。仅从认证用户的个人技能目录读取，不接受目标用户参数，不回退到同名共享技能。

## 替代方案

仅下载 SKILL.md 会遗漏配套资源；复用共享导出接口会混淆来源和权限。个人导出采用独立路由，复用现有下载响应与临时文件清理机制。

## 后果

个人工作区是可写输入，归档通过 no-follow 目录及普通文件句柄读取，拒绝符号链接和特殊文件。打包失败不返回不完整 ZIP，生成临时文件在失败或响应完成时清理。归档只包含技能目录文件，不附加平台账号及共享权限元数据。

## 验证

- Linux 隔离容器运行 `pytest test/unit/services/test_personal_skill_export.py test/unit/services/test_skill_service.py test/unit/routers/test_skill_router.py -q`：99 项通过。检查真实 ZIP 字节、二进制资源、空目录、脚本执行位、用户隔离、非法 slug、符号链接及特殊文件拒绝、失败清理，以及临时文件创建和 ZIP 写入磁盘故障的服务器异常类别。
- 独立 PostgreSQL 16 与真实 Uvicorn HTTP 服务运行 `PERSONAL_EXPORT_TEST_POSTGRES_URL=... pytest test/integration/services/test_personal_skill_export_http.py --confcutdir=test/integration/services -q`：普通用户下载、匿名及无效凭据拒绝、管理员跨用户拒绝、归档内容与响应完成清理、磁盘写入故障返回 500 并清理通过。`--confcutdir` 避开与本用例无关的全平台沙盒清理 fixture；测试使用独立空数据库，未连接生产数据库。
- 前端 `pnpm run test:unit`：343 项通过；`pnpm run lint:check` 与 `pnpm run build` 通过。
- 工程契约检查通过；修改的 Python 文件 Ruff 检查及格式检查通过；文档 `pnpm run build` 通过。
- Playwright 挂载实际个人技能列表与预览组件，使用模拟 API 响应验证下载文件名、下载 ZIP 字节和资源内容、404 提示及按钮恢复。截图位于本地 `output/playwright/personal-skill-export.png` 与 `personal-skill-export-error.png`，不作为后端权限的替代证据。
- 全平台个人技能安装生命周期测试增加导出断言，尚未在完整部署环境运行；本机没有 Docker，未执行 Compose 全量后端 unit。工程契约 unit 在 Windows 有既有的路径分隔符和符号链接权限失败。
