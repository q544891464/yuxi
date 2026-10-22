# Basic 侧栏技能配置

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/skill_navigation_service.py

## 问题

Basic 消费端直接列出可访问技能，管理员缺少组织分组、绑定入口、排序及预设任务指令的设置入口。普通用户需要在同一设置位置管理个人技能。

## 决策

### 实现方案

设置中的“侧栏技能”对登录用户开放。管理员编辑共享导航树，普通用户复用个人技能管理卡片，共享技能保持既有只读权限。菜单节点包含名称、分组、绑定技能、可选的材料及用途说明、预设提示词和通用角色范围；不预置行业内容、行业角色或工作区。

导航配置保存在既有 ConfigOption JSON 中。service 拥有树结构、共享技能绑定及角色裁剪，repository 在锁定行时刷新 ORM 实体并使用 revision 比较后更新，避免并发编辑覆盖。未配置时继续展示可访问技能列表，显式保存空树只隐藏共享菜单；当前用户的个人技能独立列出。移除节点仅删除导航入口。

SettingsModal 惰性挂载对应界面；配置保存或退出已访问的设置页后刷新导航 store 与技能列表。store 在账号或角色变化时清空缓存，拒绝迟到响应。消费端携带入口 id 和真实技能 slug，聊天页核对当前可访问列表及员工已启用技能，再展示说明并预填引用与提示词。已有用户输入保持保留，自动生成的草稿可在切换入口时替换，发送清空后同步清理自动草稿记录。菜单可见范围不授予技能调用权限。

## 替代方案

- 只增加到技能管理的跳转无法提供共享菜单分组、排序及任务指令。
- 新增用户收藏字段需要改变用户配置 schema，且不符合既有侧栏设置语义。
- 原样复制行业版本会带入业务角色与专属流程；通用树与既有个人技能管理构成更小边界。

## 后果

管理员保存的是一份全局导航树，角色与技能 ACL 在读取时共同裁剪。显式空树与从未配置保持可区分。三个 API 不新增表或迁移；共享菜单不包含个人技能绑定。未来新增行业流程需要独立决定，不通过默认菜单混入通用版本。

## 验证

- Passed：前端 lint、生产 build、相关菜单/提示词/store/设置与编辑器单元测试；真实 Chrome 在 1280、1920、1024、768、375 宽度验证添加分组、绑定入口、409 后重试、保存刷新、页面重新加载、普通用户设置与预设提示词；浅色与深色截图已检查。浏览器使用隔离接口夹具，不写业务环境。
- Passed：正确 Basic 源码快照在隔离 Linux 中运行 pytest -c pyproject.toml test/unit -m "not slow"，2621 passed；相关 service/router 18 passed；python -m unittest scripts.test_verify_engineering_contracts，62 passed。Windows tar 副本按 Git 记录恢复 shell executable 位和 LF，未更改源码以适应测试。
- Passed：test/integration/api/test_skill_navigation_http.py 的 4 项通过真实 TCP HTTP、JWT/数据库鉴权与临时 PostgreSQL 验证保存回读、普通用户拒绝、权限裁剪、显式空分组及两个独立 session 的旧 revision 拒绝。最小 FastAPI 装配复用实际 auth/system 路由和数据库依赖，替换全局沙盒清理 fixture；不代表完整 shipping lifespan 或 worker E2E。
- Passed：工程契约 verifier、补丁空白检查及 node node_modules/vitepress/bin/vitepress.js build 文档构建。
- 完整 pnpm run test:unit：462 项中 461 passed、1 failed。唯一失败是未修改的知识库详情静态测试仍期待固定 extensions 返回路径，与已有消费端返回函数不符；对应源码与测试对 HEAD 均无差异。本变更不把该基线失败记为通过。
- Not run：完整模型调用、worker E2E；此功能不修改运行投递或模型接口。
