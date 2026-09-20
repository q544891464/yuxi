# 对话运行计时归属线程状态

状态：implemented
类型：bug-fix
Owner：web/src/composables/useAgentThreadState.js

## 问题

生成回复的计时起点由 `AgentChatComponent` 的组件级变量保存。用户在运行期间切换到其他对话再返回时，当前线程的加载状态重新变为 true，组件监听器把起点重置为当前时间，导致“已思考”时长从零开始。

## 决策

回复计时起点和本轮请求标识保存在各线程的运行状态中，由运行流首次进入 loading 时写入。界面计时器只根据当前线程的绝对起点刷新显示；切换会话或 keep-alive 暂停只停止 interval，不修改起点，组件停用期间状态监听也不会重新创建 interval。新请求即使在上一轮仍显示 loading 时接续启动，也会因请求标识变化覆盖旧起点。

## 替代方案

- 把计时值写入 localStorage：拒绝，运行时状态已有线程级 Owner，浏览器持久化会产生过期清理问题。
- 切换回来时沿用组件级秒数：拒绝，多个并发线程会共享错误的计时状态，而且页面隐藏期间不会推进。
- 从消息数量或 SSE 重连时间推算：拒绝，这些时间不是当前运行的开始事实。

## 后果

- 每个运行中线程拥有独立起点，同时运行或来回切换不会串线。
- interval 只负责刷新界面，停留在其他会话期间仍由绝对时间差补齐经过时长。
- 运行在后台结束后旧起点可以暂存在线程状态中，但 loading 已关闭，不会显示；同线程下一次请求进入 loading 时会按请求标识覆盖它。

## 验证

- `node --test test/unit/replyElapsed.test.js test/unit/consumerWorkspaceRoutes.test.js`：7 项通过，覆盖同一请求重连、不同线程、队列接续的新请求、无效起点和时钟回拨。
- `pnpm run lint:check`：通过。
- 真实 Chrome：运行中显示 `7s`，切换到另一会话再返回后显示 `55s`，没有从零开始；截图为 `output/playwright/reply-elapsed-after-thread-switch.png`。
