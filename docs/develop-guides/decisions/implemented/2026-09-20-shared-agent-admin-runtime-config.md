# 共享 Agent 的管理员配置对普通用户生效

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/agents/context.py

## 问题

Agent Context 字段的 `metadata.auth` 同时被用于控制配置界面可编辑性和运行时取值。
管理员为共享 Agent 设置摘要阈值等运行参数后，普通用户执行时这些字段会被删除并回落到默认值，
导致管理页面显示 999K，而普通用户实际仍按 100K 运行。

## 决策

保留现有按角色过滤接口，继续用于配置展示和非可信输入校验。显式的可信持久配置模式只用于运行装配：
只有从已授权 Agent 记录读取并进入运行装配的 Context 才保留管理员字段；Skills、工具、知识库、
MCP 和子智能体仍按当前执行用户的可见范围重新归一化。普通用户仍看不到、不能编辑管理员字段。

## 替代方案

- 把 `summary_threshold` 改成普通用户可配置：拒绝，会改变管理员集中管理契约。
- 只修前端显示成 999K：拒绝，真实运行仍在 100K 压缩，属于伪装修复。
- 运行时完全跳过用户过滤：拒绝，会使资源型字段绕过当前用户可见性检查。

## 后果

管理员集中配置共享 Agent 的摘要阈值、执行步数等运行参数后，所有有权调用该 Agent 的用户使用同一配置。普通用户仍看不到也不能编辑管理员字段。资源型字段继续按执行用户的当前可见范围收敛。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 普通用户执行共享 Agent 时继承管理员保存的摘要阈值 | 管理字段被角色过滤后回落默认值 | `normalize_agent_context_config` 与 Run manifest 装配 | Linux 生产镜像定向测试；生产 `user001` 新 Run 与 checkpoint 回读 | 关闭可信持久配置模式后 unit 断言恢复缺字段 | Passed |
| 普通用户仍不能查看或修改管理员字段 | 为修运行值而扩大编辑权限 | Context schema/config API | 既有 auth unit；Linux 生产镜像定向测试 | 普通用户配置项仍不包含摘要阈值 | Passed |
| 资源仍按执行用户授权范围收敛 | 可信配置模式错误保留越权 Skill/工具 | Context 资源归一化 | `test_context_auth.py` 以不可见资源验证归一化 | 配置 `missing` 工具与 Skill 后结果不得保留 | Passed |

- `ruff check`：修改涉及的 Python 文件通过。
- 生产同版本 Linux 镜像执行 Context、主动压缩与 manifest 定向测试：26 项通过。
- 生产环境以普通用户新建会话并只发送首条消息：Run `completed`；manifest 的 `summary_threshold=999`，checkpoint 的 `summary_trigger_tokens=1022976`（999K），总耗时约 6 秒。
- 工程契约检查通过。工程契约 unittest 在 Windows 因创建符号链接权限和路径分隔符断言失败，未计为通过。
