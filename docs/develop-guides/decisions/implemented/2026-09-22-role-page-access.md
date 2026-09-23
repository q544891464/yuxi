# 角色页面入口限制

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/page_access_service.py

## 问题
督查人员可以从登录跳转和手输地址进入其他工作区，需要超级管理员按角色配置页面范围及默认入口。

## 决策
新增受超级管理员保护的 PostgreSQL 页面配置，按内置页面目录配置普通用户、督查人员和管理员；超级管理员不可限制，避免锁死配置入口。后续扩展了[稽查和审理角色](./2026-09-23-inspection-review-roles.md)的独立规则。督查人员默认仅允许 /chat/ducha 及其对话详情。服务端每次导航计算当前角色可用页面，前端守卫和菜单使用同一结果；读取失败显示可重试页面，不放行或白屏。

页面入口配置不授予额外数据权限；已有 API、资源、部门权限继续执行。页面地址只能从内置目录选择，不支持外部 URL；配置版本冲突拒绝覆盖。

## 替代方案
只隐藏菜单无法阻止手输地址；按 Referer 拦截共享对话 API 无法可靠区分页面，且会破坏督查页面复用的能力。因此保留资源授权边界，通过服务端页面决策和导航守卫限制页面入口。

## 后果
普通用户、稽查人员、审理人员和管理员默认为现有普通页面范围；督查默认限制。已有登录态在下一次导航读取最新配置。OIDC 回调与共享登录仍需完成认证后再应用页面限制。

## 验证
服务与真实 PostgreSQL/HTTP 验证配置权限、保存重读、版本冲突及无效配置；前端验证督查登录、深链接、禁止地址重定向、菜单过滤、超级管理员配置和读取失败。


验证结果（2026-09-22）：

- `node --test --test-concurrency=1 "test/**/*.test.js" "test/**/*.spec.js"`：前端全量 398 项通过；追加默认首页回归后，路由及菜单相关 16 项通过。
- 前端 ESLint、Vite build、VitePress build、`python scripts/verify_engineering_contracts.py`、`git diff --check` 通过。工程契约 unittest 在 Linux 62 项通过；Windows 存在路径分隔符与符号链接权限差异。
- 隔离 PostgreSQL + 实际认证 HTTP：`test_page_access.py`、`test_ducha_service.py`、`test_skill_navigation_http.py` 共 27 项通过，覆盖非超级管理员拒绝修改、通用配置不泄露规则、持久化重读与旧版本拒绝。
- Playwright 加载真实 Vue 页面并隔离业务 API：督查身份手输其他工作区回到督查首页、督查对话详情保留、超级管理员打开配置并保存、空页面列表禁用保存均通过。浏览器业务 API 使用 fixture；未声称生产环境已验证。
- 后端全量 unit 已尝试但未通过：补齐隔离目录配置后，首个失败为未修改的 `test_shell_initialization_validation_accepts_distinct_strong_secrets`，Linux 执行 `scripts/init.sh` 时遇到 CRLF（343 项通过后停止）。此前全量运行未收敛，已停止隔离测试容器。未将全量后端回归标为通过。
- 本次尚未部署。新增页面限制只决定 UI 入口，资源授权仍由原后端边界执行。
