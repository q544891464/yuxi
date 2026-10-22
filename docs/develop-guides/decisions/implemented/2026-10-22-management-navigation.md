# 知识库与技能管理入口拆分

状态：implemented
类型：simplification
Owner：web/src/router/index.js

## 问题

管理员从主页进入技能管理时需要直接管理技能，知识库管理需要独立列表与详情返回路径。侧栏技能配置属于技能管理任务，设置弹窗中的独立入口增加发现成本。管理工作台入口重复了主页已有导航。

## 决策

主页与用户菜单移除管理工作台入口，既有 `/agent` 管理员会话深链接继续可用。知识库管理只显示知识库，技能管理显示技能、工具、MCP 和侧栏技能配置。普通用户从技能管理访问个人技能，工具、MCP 和共享侧栏配置仅管理员可见。资源授权、员工技能启用范围、配置数据结构和运行链路保持既有契约。

### 实现方案

`router` 将知识库列表和详情装配到 `/knowledge`，旧知识库扩展链接重定向到对应页面并保留详情查询参数与 hash。`DataBaseView` 提供知识库管理标题，`DataBaseInfoView` 根据具体路由和当前身份返回管理列表或只读列表；普通用户从旧详情链接返回时进入可访问知识库。评估详情、员工配置表单、知识库删除及消费端管理按钮直接使用管理列表的命名路由。

`ExtensionsView` 使用 `/extensions`，默认显示技能，管理员可切换工具、MCP 和复用的 `SkillNavigationSettings`。非法或越权 Tab 归一为技能；小屏标题与 Tab 分行。`AppLayout` 提供独立知识库管理与技能管理入口，普通用户保留技能管理入口；`UserInfoComponent` 删除工作台入口。`SettingsModal` 移除侧栏技能面板和相关刷新依赖。

配置保存与菜单刷新由已有 `SkillNavigationSettings` 和 Store 拥有。版本冲突保留原配置，加载失败禁止保存，并呈现可重试错误。后端仍拥有 API、ACL 与持久化；迁移入口不创建新的授权或数据副本。这项决定取代[员工侧栏决策](./2026-10-22-employee-chat-sidebar.md)中的工作台可见入口。

## 替代方案

- 保留混合页，仅调整默认 Tab：入口仍不能限定资源类型。
- 通过混合页查询参数隐藏 Tab：知识库和技能的页面身份及详情返回仍耦合。
- 删除整个管理员会话路由：会破坏已有深链接，超出重复导航清理范围。
- 保留设置弹窗中的侧栏技能副本：增加两个配置入口的发现和维护负担。

## 后果

知识库管理有独立 URL，旧知识库链接有明确跳转。侧栏技能只有技能管理中的配置入口，普通用户仍可管理个人技能。前端修改不改变数据库或后端部署，发布仅替换前端资源。

## 验证

旧能力不存在：`AppLayout` 和 `UserInfoComponent` 不再包含管理工作台文本，`SettingsModal` 不再依赖侧栏技能组件和 Store，`ExtensionsView` 不再导入或装配知识库列表。源码搜索、相关 unit 和浏览器 DOM 均已检查；旧知识库 URL 仅保留为路由兼容入口。

重新引入条件：只有出现主页无法承载的独立管理任务，才重新评估工作台入口；侧栏技能继续只有一个配置入口。

- `pnpm run test:unit`：487/487 通过。知识库只读连接器的旧断言随返回路径更新，仍验证禁止进入详情和只允许授权编辑。最后的普通用户详情返回与内部调用收敛后，`node --test test/unit/basic_navigation.test.js test/unit/settings_lazy_mount.test.js test/unit/management_navigation.test.js test/unit/knowledge_detail_layout.test.js test/unit/knowledge_evaluation_workspace.test.js test/unit/agentRuntimeConfigVisibility.test.js test/unit/skill_navigation_editor.test.js`：27/27 通过。路由负控在实现前因缺少独立页面和旧链接跳转正确失败。
- `pnpm run lint:check`、`pnpm run build` 通过。
- `npx --yes --package @playwright/cli playwright-cli --session management run-code --filename web/test/browser/managementNavigation.js` 在生产构建预览通过。真实 DOM 覆盖独立页面、管理与普通用户详情返回、旧链接、只读连接器跳转、侧栏配置保存后重载及菜单刷新、冲突和加载失败、删除重复入口、权限投影、浅深色与手机布局。写入仅在隔离 API fixture 中发生，不修改线上配置；不替代后端持久化与授权验证。
- `python -m unittest scripts.test_verify_engineering_contracts`：Linux 62/62 通过；Windows 因缺少符号链接权限有一项环境错误。使用未改动的相同脚本在 Linux 复验。
- `python scripts/verify_engineering_contracts.py` 通过，检查 176 份决策和相关链接、工程边界；文档目录 `pnpm run build` 通过。
- 本机无 Docker，后端源码未修改；以部署快照中相同后端源码在独立无网络容器执行 `python -m pytest test/unit -m "not slow" -p no:cacheprovider`，2621 项与 7 个子测试通过。源码只读挂载，技能与运行目录使用独立临时路径，不访问线上业务数据。真实模型与运行链路不在本次改动或验证范围。
