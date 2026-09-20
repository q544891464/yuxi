# Dashboard 会话 Token 统计读取运行事实

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/storage/postgres/models_business.py

## 问题

Dashboard 的会话列表、会话详情和会话分析从 `conversation_stats.total_tokens` 读取 Token 数。当前运行链在 AgentRun 终态持久化可靠的 `token_usage`，没有同步维护旧统计列，导致所有会话显示为 0。生产只读核对显示 `conversation_stats` 的 166 条记录均为 0，而 457 条 AgentRun 中有 424 条带非零用量。

## 决策

Dashboard 按 `AgentRun.conversation_id` 聚合 `token_usage.total.total_tokens`。列表、详情和会话分析使用同一运行事实；仅当会话没有任何带 Token 总量的 Run 时，兼容读取历史 `conversation_stats.total_tokens`。失败、中断和完成的 Run 都保留已经实际消耗且被终态持久化的用量。

## 替代方案

- 在每次 Run 结束时继续累加 `conversation_stats`：拒绝，这会建立第二份可漂移的汇总事实，并需要处理终态幂等、重试和历史回填。
- 前端从消息文本估算 Token：拒绝，文本估算不等于模型供应商返回的输入、输出用量，也会遗漏工具循环和上下文。
- 一次性回填旧统计表后保持原查询：拒绝，只能修复已有数据，后续运行仍会再次变为不一致。

## 后果

- 会话列表与分析会反映模型运行的实际累计用量，不再固定为 0。
- 同一会话有多次 chat/resume Run 时累加每次 Run 的用量。
- 没有可靠 usage 的历史会话仍可使用原有统计值；两种来源不会在同一会话重复相加。

## 验证

- `pytest test/unit/services/test_dashboard_service.py -q`：Linux 容器中 8 项通过；用完成与中断 Run 的 50 Tokens 覆盖旧统计值 3500，忽略无可靠 usage 的 Run，并验证列表、详情、总汇与 Agent 分布结果一致；另覆盖旧统计 NULL。
- Ruff check 与 format check：通过。
- 生产 PostgreSQL 只读核对确认旧统计列全为 0，AgentRun 已持久化非零用量。
