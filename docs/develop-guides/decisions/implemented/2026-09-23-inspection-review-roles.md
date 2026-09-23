# 增加稽查与审理业务角色

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/page_access_service.py

## 问题

平台只有普通用户、督查人员和管理员等身份，无法给稽查人员、审理人员单独分配账号及页面、技能和文书接收范围。现有已保存的角色页面配置只有三个业务角色，直接增加必填规则会使登录和管理页读取失败。

## 决策

新增稳定角色标识 `inspector`（稽查人员）与 `reviewer`（审理人员），保留现有 `user` 身份及账号。两个角色默认可进入既有稽查工作区和普通用户页面，不开放督查工作区或管理页；审理不另建页面。`auth_router` 与 `ducha_service` 拥有账号创建、编辑和部门边界，`page_access_service` 拥有工作区规则，`skill_navigation_service` 拥有侧栏角色可见性，`formal_document_service` 拥有文书流程范围。后台界面提供相应角色选项。

沿用[角色页面入口限制](./2026-09-22-role-page-access.md)的服务端决策与导航守卫，不以菜单隐藏代替授权。

读取旧页面配置时只为缺失的新角色补入默认规则，不修改存储值和 revision；下一次保存完整配置。角色切换只在已有业务角色之间进行。

## 替代方案

将现有 `user` 重命名为稽查人员会隐式改变现有用户的身份与权限，也无法区分审理人员。只在前端增加选项无法通过后端身份和页面鉴权。为审理人员新建页面超出本次角色请求。

## 后果

已保存的侧栏菜单不会自动授予新角色可见性；管理员需要在“侧栏技能”中明确选择。新角色不会自动获得既有文书的接收资格。`user` 身份及其原有权限保持不变。

## 验证

- 隔离 PostgreSQL、真实 HTTP：`test_skill_navigation_http.py` 与 `test_formal_documents_http.py`，验证账号创建、切换、旧页面配置读取、菜单过滤及稽查到审理文书移交；配套单测合计 56 个通过。旧页面配置读取不写回，督查/管理入口拒绝新角色。
- 前端：`npm run lint:check`、`npm run test:unit`（412 个通过）及 `npm run build` 通过。Playwright 使用本地页面和模拟 API，在添加用户下拉及角色页面权限中确认两种新角色均显示；没有操作真实账号。
- 本地截图保存在忽略目录 `output/playwright/inspection-review-user-roles.png` 与 `output/playwright/inspection-review-roles.png`，仅作为本轮人工界面核对证据，不随代码发布。
- 后端隔离 Linux 全量非慢单测为 2108 通过、56 跳过；`ruff check` 通过。`python scripts/verify_engineering_contracts.py` 通过，工程契约单测在 Linux 为 62 通过。
