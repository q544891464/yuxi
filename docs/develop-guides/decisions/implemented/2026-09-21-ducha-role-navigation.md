# 督查工作区与侧栏角色可见性

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/skill_navigation_service.py

## 问题

督查人员需要独立品牌入口，管理员需要按角色发布侧栏技能树。

## 决策

`ducha` 是普通权限等级的角色。管理员通过设置中的用户管理，在普通用户与督查人员之间切换身份，部门管理员只管理本部门人员。该切换不修改管理员或超级管理员身份。`ducha_service` 拥有角色切换和页面访问判断，用户编辑接口拥有保存与审计事务。

`/chat/ducha` 及其会话子路由使用督查文案，不展示资源统计。前端守卫每次进入该路由都调用受控配置接口，后端根据数据库当前身份只允许 ducha、admin、superadmin。页面复用当前用户的项目、会话及资源权限，不建立督查与稽查的数据分区。

导航节点增加 `visibleRoles`，缺省对全部角色可见，空列表隐藏。父节点不可见时整个子树隐藏；管理端独立读取完整配置，普通菜单接口在服务端过滤。导航可见性不替代技能本体调用授权。保存后强制发起新的角色过滤读取，旧请求不能覆盖新配置；刷新失败与保存失败分别提示。账号或角色变化清除缓存。

## 替代方案

独立部署会复制运行与持久化链路；通用多角色系统超出单一督查角色需求。仅前端隐藏无法保证未授权角色取不到页面配置和菜单。

## 后果

既有配置缺省可见范围保持不变，管理员按需配置。用户管理不提供普通用户自助授权接口。角色变更由每次请求重新读取数据库身份执行，既有登录令牌不缓存角色。督查人员不获得后台管理或知识库写入特权。

## 验证

- Linux 独立容器与独立 PostgreSQL：`python -m pytest test/unit/services/test_skill_navigation.py test/unit/services/test_ducha_service.py test/integration/api/test_skill_navigation_http.py -q --confcutdir=test/integration/api -p no:cacheprovider`，23 passed。独立 fixture 自建 HTTP 服务与数据库表，排除通用 integration 清理器以避免接触共享沙盒；验证角色授予/撤回、401/403、管理员完整配置、菜单父子过滤及数据库回读。
- 前端 `node --test --test-concurrency=1 "test/**/*.test.js" "test/**/*.spec.js"`，369 passed；最终新增与相关三个测试文件定向执行，9 passed。`node node_modules/eslint/bin/eslint.js . --max-warnings=0` 与 `node node_modules/vite/bin/vite.js build` 通过。
- Playwright 浏览器使用 API fixture 检查 1280×720、1920×1080 页面，督查品牌、隐藏统计、新建/会话路由、原聊天页统计以及管理员角色多选保存通过。未授权接口响应触发返回普通聊天页；无登录令牌跳转登录页。截图在本地 `output/playwright/ducha-*.png`，不作为服务端授权证据。
- 工程契约检查通过；契约测试 Windows 有路径/符号链接平台失败，Linux `python -m unittest scripts.test_verify_engineering_contracts` 62 passed。文档 VitePress build、定向 Ruff 与 diff whitespace 检查通过。
- 全量后端 unit 在独立镜像中尝试：1525 passed、56 skipped、19 failed，worker 测试停留超过七分钟后中断。失败涉及验证挂载目录写权限和 Office 读取，未证明全量回归通过。该环境结果不替代独立 HTTP 与相关 unit 证据；生产部署和真实模型对话尚未执行。
