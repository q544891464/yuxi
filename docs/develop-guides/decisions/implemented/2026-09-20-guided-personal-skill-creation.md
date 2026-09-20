# 对话式个人技能创建入口

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/service.py

## 问题

业务侧栏的“添加技能”原来跳转到扩展后台，打断用户对话；普通用户也看不到“设置 → 侧栏技能”，无法从该入口维护个人技能。共享技能属于平台资源，普通用户必须只能查看，不能修改、启停或删除。原有共享权限解析允许普通用户因 `manage_scope` 获得管理权，不能满足这一边界。

## 决策

“添加技能”进入新对话，并在输入框引用当前智能体可访问的 `skill-creator-v2`（全局 Skill Creator），填入中文创建引导，由用户确认发送后沿用现有 AgentRun、权限和个人工作区链路。入口不自动发送，也不伪造不可访问的技能；缺失、禁用或未开放时保持不可调用状态。

“设置 → 侧栏技能”对所有登录用户可见。管理员继续使用全平台导航配置；普通用户复用技能卡片页导入、改名、导出和删除自己的个人技能，共享技能只读展示。

后端以 `user_can_manage_skill` 作为共享技能写权限 Owner：管理员仍按共享管理范围获得权限，普通用户只可管理本人创建且来源为 `personal` 的技能，即使共享技能的历史 `manage_scope` 包含该用户也不得写入。前端消费后端 `can_manage`，隐藏或禁用共享技能写操作。

权限事实由 `backend/package/yuxi/agents/skills/service.py` 拥有；聊天入口与普通用户设置展示分别由 `web/src/layouts/AppLayout.vue` 和 `web/src/components/SettingsModal.vue` 拥有。

## 替代方案

继续跳转扩展后台不能满足对话式引导；新增独立向导会复制 SkillCreator 的需求收集逻辑。只在前端隐藏共享技能操作无法阻止直接 API 调用，因此必须同时收紧后端权限。完全删除 `manage_scope` 会影响管理员现有授权模型，故保留管理员语义。

## 后果

普通用户能在对话中创建个人技能，并在设置页管理个人技能；共享技能保持可查看、可调用但不可编辑。历史上通过 `manage_scope` 授予普通用户的共享技能写权限停止生效，管理员权限不变。当前智能体未开放 `skill-creator` 时，入口不会自动扩大能力。

## 验证

- `node --test test/unit/skillEntries.test.js test/unit/projectConversationGroups.test.js test/unit/settings_lazy_mount.test.js`：20 项通过，覆盖虚拟 `skill-creator` 入口、非自动发送草稿链路和普通用户设置面板。
- `pnpm run test:unit`：361 项通过。
- `pnpm run lint:check`：通过。
- `NODE_OPTIONS=--max-old-space-size=4096 pnpm run build`：通过。
- `uv run ruff check package/yuxi/agents/skills/service.py test/unit/routers/test_skill_router.py`：通过。
- 生产同版本 Linux API 镜像隔离挂载修改后源码执行 `PYTHONPATH=/app:/app/package uv run --no-sync pytest /tmp/test_skill_router.py -q`：16 项通过，覆盖普通用户即使出现在共享 `manage_scope` 中仍为只读，以及本人个人技能可管理。
- Playwright 真实页面（普通用户）：点击“添加技能”后 URL 为 `/chat?skill=create-personal-skill`，输入框出现 `@skill:skill-creator-v2` 和完整中文引导词，发送按钮可用且没有生成对话；“设置 → 侧栏技能”显示个人技能上传/远程安装入口，共享与内置技能的启停按钮均禁用。截图保存于本地验证产物 `output/playwright/personal-skill-chat-entry-ready.png`、`output/playwright/personal-skill-settings.png`。
- 管理员全局侧栏技能编辑器由设置组件挂载测试覆盖；管理员分支未修改。
