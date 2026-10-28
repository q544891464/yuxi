# 中间件

中间件把文件、Skills、子智能体、上下文压缩、审批和用量统计接到 LangGraph Agent。它们在模型调用、工具调用或 state 更新的边界运行，让不同 Agent 复用同一套能力。

内置 `ChatbotAgent` 和 `SubAgentBackend` 都在 `get_graph()` 中组装中间件。Graph 创建前，系统先完成用户资源和权限的归一化；中间件不应绕过这一步重新决定授权。

## Graph 创建前的准备

`prepare_agent_runtime_context` 会根据当前用户和 Agent 配置：

- 过滤内置工具、知识库、MCP、Skills 和子智能体；
- 生成 `_visible_knowledge_bases`；
- 展开 Skill 依赖，生成 `_effective_skill_slugs` 和 `_runtime_skills`；
- 使用系统默认模型补齐空的模型配置。

随后，工具解析器准备可执行工具，`build_prompt_with_context` 生成系统提示词，Agent 再创建 Graph。工具执行时仍需检查具体目标，准备阶段的资源快照不是授权替代品。

## 内置中间件顺序

`ChatbotAgent` 的组合顺序如下；可选项只在对应能力启用时加入，序号不代表删去可选项后的数组下标：

| 顺序 | 中间件 | 作用 |
| --- | --- | --- |
| 1 | `ToolErrorGuardMiddleware` | 隔离普通工具异常，保留取消与 interrupt 的传播 |
| 2 | `SteerMiddleware` | 在安全边界发现待接替请求 |
| 3 | `create_agent_filesystem_middleware` | 提供 Workdir、User Data、Skills 文件后端，并卸载过大的工具结果 |
| 4 | `SkillsMiddleware` | 注入 Skill 说明，按激活状态开放依赖 |
| 5 | `YuxiMemoryMiddleware` | Memory 开关开启且 `MEMORY.md` 有内容时，注入用户记忆并提供受限工具 |
| 6 | `YuxiSubAgentMiddleware` | 主智能体有可见子智能体时提供子智能体生命周期工具 |
| 7 | `YuxiSummarizationMiddleware` | 先确定性压缩工具结果，仍达到同一阈值时生成摘要 |
| 8 | `TodoListMiddleware` | 提示模型分阶段及时更新待办，并保存状态供面板展示 |
| 9 | `PatchToolCallsMiddleware` | 修正部分工具调用消息形态 |
| 10 | `NetworkRetryMiddleware` | 网络错误按预算、其他可重试模型错误按次数重试，耗尽后抛出异常 |
| 11 | `ImageInputCompatibilityMiddleware` | 桥接工具读取图片与模型输入格式；必要时回退 OCR |
| 12 | `TokenUsageMiddleware` | 记录近似上下文和主模型实际用量 |
| 13 | 工具审批 middleware | 默认模式下拦截写文件、编辑文件和执行命令 |
| 14 | `ContextBudgetMiddleware` | 供应商显式启用 tokenizer 时，在所有提示注入后校验真实输入和输出预算 |

`SubAgentBackend` 复用文件、Skills、Summary、待办、重试和用量等能力，但不挂载子智能体 middleware，并过滤不适合子智能体的敏感或交互工具。

模型重试耗尽后，异常进入 Run 失败通道，持久化 `failed` 状态与错误原因；已有部分输出保留错误元数据。子 Run 的失败通过 `subagent_await` / `subagent_status` 返回给父智能体，由父智能体决定后续处理。最终正常回答仍须满足同 Run 的 model lifecycle 审计关联。

主、子智能体使用相同的待办提示：复杂任务先建立3–5个阶段，首项立即进入进行中；阶段完成时先更新当前项及下一项，再开展后续工作。交付文件实际生成并检查后才标记完成，未完成或等待补充的工作保留未完成状态。这是模型执行指引，模型仍可能延迟调用更新工具；状态传播测试不代表任意模型的业务进度都能及时更新。

## Skills 和知识库

Skills middleware 将 Skill 说明按模型请求注入：预加载 Skill 从首轮开放工具和 MCP 依赖，普通 Skill 在模型读取对应 `SKILL.md` 后激活，再开放声明的依赖。Agent 显式选择的 MCP 服务器从运行开始提供工具。

知识库能力由内置 `knowledge-base` Skill 提供。它的工具是否注册、模型是否可见、参数是否能访问目标知识库分别由工具组装、Skill 激活和知识库权限检查负责。完整链路见[工具系统](./tools-system.md)和[知识库机制详解](../mechanisms/knowledge-base.md)。

## 文件和附件

文件中间件在工具返回后按 `tool_token_limit × 1024` 个近似 token 判断是否卸载大结果，默认3K。管理员可在员工配置中调整该值，主、子智能体使用各自保存的配置；提高阈值会让更多工具正文直接进入上下文。现有文件工具分页及 `open_kb_document` 豁免继续生效，整体输入仍按已启用的上下文预算检查。摘要阶段的工具预览长度由 `summary_tool_result_token_limit` 单独控制，详见[上下文压缩机制](../mechanisms/context-compression.md)。

附件确认后写入当前 Project Workdir。每次 Run 会把线程历史附件的文件名和实时路径加入本轮用户消息，让模型按需调用 `read_file`；持久化 Message 仍保存原始文本，不会把这段模型专用路径混进用户可见消息。

普通 Agent 和子 Agent 使用根 Conversation 的同一个 `runtime_scope_id` 和 Workdir。子 Agent 的 child thread 只隔离 LangGraph checkpoint，不隔离共享文件。Viewer、附件和 artifact API 直接访问 UserWorkspace 的持久文件，不需要创建 file-bridge Sandbox。

## 子智能体

主智能体配置了可见子智能体时，middleware 提供 `subagent_start`、`subagent_status`、`subagent_cancel` 和 `subagent_await`。`subagent_start` 立即返回子 Run 身份，`subagent_await` 按需等待；查询和取消均按 `run_id` 执行。子智能体使用自己的 Context 和 checkpoint，但继承发起用户的权限、Workdir 和 execution runtime。

详细的调用、busy、结果和文件边界见[子智能体](./subagents-management.md)。

## Summary 上下文压缩

Summary 在文件和 Skills 等中间件之后运行。请求达到唯一压力阈值后，它先为当前模型请求精简工具结果并重新计量；仍达到同一阈值时才写入历史文件、生成摘要并更新 checkpoint。它不会删除 PostgreSQL 聊天消息，也不会把内部摘要模型调用当作用户可见回复。支持主动压缩的 Agent 复用同一摘要器，并通过 service 在空闲线程的 canonical graph state 上更新 checkpoint。

参数和状态细节见[上下文压缩机制](../mechanisms/context-compression.md)。

## Token 用量

`TokenUsageMiddleware` 同时记录：

- 近似上下文 token，用于状态面板；未启用 tokenizer 的供应商也用近似计数触发摘要，启用方式见[上下文压缩机制](../mechanisms/context-compression.md#模型计数口径)；
- 主 Agent 模型返回的 `usage_metadata`，按最近调用、当前 Run、线程和模型分桶保存。

`siliconflow-cn` 和 `siliconflow` 当前位于 Provider 用量黑名单：这两个供应商仍可提供近似上下文统计，但不会写入最近调用、Run 或线程的 Provider 实际用量聚合。其他能返回兼容 `usage_metadata` 的供应商才会进入这组实际用量统计。当前口径也不包含 Summary 内部摘要模型调用。Run 终态时，worker 把与当前 `run_id` 匹配的 state 快照写入 `AgentRun.token_usage`；父 Run 和子 Run 分开保存。

## 新增中间件时

先说明它要改变哪一条边界：Prompt、模型调用、工具调用、文件访问、state 或观测。资源筛选和权限收敛放在 Graph 创建前；文件读写和工具结果卸载优先复用现有 filesystem middleware；新增模型可见输入或副作用时补充对应测试和失败案例。

实现入口：[ChatbotAgent graph](https://github.com/xerrors/Yuxi/blob/main/backend/package/yuxi/agents/buildin/chatbot/graph.py)、[中间件目录](https://github.com/xerrors/Yuxi/tree/main/backend/package/yuxi/agents/middlewares)。
