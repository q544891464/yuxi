# 技能展示名编辑

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/service.py

## 问题

SkillCreator 创建的技能通常使用英文名称。技能 slug 同时承担目录、调用、依赖和导入更新标识，不能用重命名 slug 的方式满足中文展示需求。

## 决策

`SKILL.md` frontmatter 的 `name` 是展示名，`slug` 是稳定内部标识。技能卡片预览为可管理且非内置的共享技能和个人技能提供“修改名称”入口。保存时校验非空和 128 字符上限，更新 `SKILL.md` 并显式固化原 slug；共享技能同时更新数据库索引。

个人技能更新只在当前用户工作区和个人技能文件锁内执行。共享技能在数据库行锁内先原子替换文件，再提交数据库；提交失败时回滚数据库并恢复原文件。内置技能和只有读取权限的共享技能拒绝改名。

## 替代方案

- 直接改 slug 会破坏目录、调用和已有绑定。
- 独立数据库 `display_name` 字段无法覆盖没有数据库记录的个人技能，导出时也需额外同步。
- 仅保存前端别名会导致选择器、运行时、导出和重新导入之间名称漂移。

## 后果

- 用户可以把英文技能改为中文展示名，已有 `@` 引用、依赖和侧栏绑定继续使用原 slug。
- 改名会规范化 `SKILL.md` frontmatter 的 YAML 格式，并为旧格式技能补写显式 slug。
- 内置技能名称继续由发布包维护。

## 验证

- `node --test test/unit/personal_skill_export.test.js`：Passed（6/6）。
- `pnpm exec eslint src/components/extensions/SkillCardList.vue src/apis/skill_api.js --max-warnings=0`：Passed。
- `pnpm build`：Passed。
- `uv run ruff check package/yuxi/agents/skills/service.py server/routers/skill_router.py test/unit/services/test_skill_service.py test/unit/routers/test_skill_router.py`：Passed。
- `python scripts/verify_engineering_contracts.py`：Passed。
- Playwright 真实页面（本地 Vite、按方法与精确路径模拟 API）验证：改名请求实际发送 `PUT /api/skills/personal/english-skill/display-name`，响应后卡片、预览标题与重新读取的 `SKILL.md` 均显示“中文技能名”，slug 保持 `english-skill`；只读共享技能和内置技能均无改名入口。截图见 `output/playwright/skill-display-name-updated.png`、`output/playwright/skill-display-name-readonly.png` 和 `output/playwright/skill-display-name-builtin.png`。
- 后端 unit/integration：Not run；Windows 主机缺少 Linux `fcntl` / `O_DIRECTORY`，且本机没有 Docker。已补充共享成功、文件写入失败、提交失败、只读、内置、跨用户个人技能和真实个人技能 HTTP 生命周期测试，交由 Linux CI 执行。
