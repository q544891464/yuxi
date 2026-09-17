# 个人技能导入更新

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/service.py

## 问题

个人技能 ZIP 已支持导出，但重新导入同一技能时仍按冲突处理，无法用修订后的内容更新已有个人技能。

## 决策

个人技能导入预览阶段根据当前登录用户的个人技能目录标记同 slug 项目为“将更新”。确认安装时，在同一用户目录内通过用户级文件锁和 pending 标记串行替换目录；中断后下次访问会恢复旧目录或清理已完成替换的备份。共享技能导入继续保留现有冲突策略。

## 替代方案

直接删除旧目录再复制会在失败时丢失可用技能；自动生成新 slug 会破坏导出 ZIP 的稳定引用。仅更新 SKILL.md 会遗漏脚本和资源，因此按完整技能目录替换。

## 后果

更新只作用于当前认证用户拥有的个人技能，仍通过现有草稿所有权和 slug、工作区路径校验执行。预览阶段不创建用户工作区，并拒绝符号链接路径；个人 Skill 的运行期预加载和 artifact 读取也复用同一用户锁。确认页显示“将更新”，结果显示“已更新”；旧目录替换过程不改变共享 Skill 数据。

导入接口的 400 仍遵循前端统一错误脱敏策略；Skill 导入页将这类通用提示转换为不含内部路径或服务端细节的结构要求，直接提示 ZIP 只能包含一个 `SKILL.md`，方便用户修正归档。

## 验证

- Linux 隔离容器运行 `test/unit/services/test_personal_skill_export.py test/unit/services/test_skill_service.py test/unit/routers/test_skill_router.py -q`：中间修订版 102 项通过；最后一次源码安全修订因远程 SSH 暂时不可达未重跑。
- 前端 `pnpm --dir web run test:unit`：344 项通过；`pnpm --dir web run lint:check` 与 `pnpm --dir web run build` 通过。
- 前端单元测试新增导入更新标记、确认按钮和结果文案断言。
- artifact 单元测试覆盖授权个人 Skill 虚拟路径的读取。
- `python scripts/verify_engineering_contracts.py` 与相关 Python Ruff 检查通过；Windows 工程契约单测仍受既有符号链接权限和路径分隔符差异影响。
- 个人导入 API 生命周期测试已覆盖预览 `personal_update`、确认 `updated` 和更新后内容读取；完整部署环境集成测试尚未执行。
