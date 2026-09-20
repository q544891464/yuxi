# 会话与项目使用可恢复归档

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/conversation_service.py

## 问题

长期积累的会话和项目持续占据侧栏主列表。删除会破坏用户继续查阅和恢复工作的能力，而仅在前端隐藏无法形成跨设备一致的业务事实。

## 决策

会话沿用已有 `active/archived/deleted` 状态。Project 状态扩展为 `active/archived/deleted`，由 storage-migrator 更新约束。归档 Project 只改变 Project 自身状态，主会话列表按 active Project 过滤，因此项目中的会话随项目隐藏；恢复 Project 后，会话保持各自原有状态。

侧栏增加“已归档”入口，分别读取已归档项目和已归档会话，并允许恢复。删除语义保持不变，归档不删除 Workdir、消息或附件。

## 替代方案

- 用浏览器本地状态隐藏：无法跨设备同步，也不是业务事实，拒绝。
- 归档项目时批量改写全部会话状态：无法区分会话原有的独立归档选择，恢复会丢失语义，拒绝。
- 新建独立 archive 表：复制现有生命周期状态并增加事务复杂度，拒绝。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 用户只能归档和恢复自己的会话、项目 | 跨用户 ID 可修改 | service + repository 用户条件 | 后端 unit 与真实 HTTP integration | 使用其他用户资源返回 404 | unit 通过；integration 已编写，待 Linux PostgreSQL 执行 |
| 归档项从主列表消失并可在已归档入口恢复 | 前端隐藏但 API 仍混入主列表 | status 查询 + 侧栏 Store | 后端 unit、前端 API unit、build | archived 状态不出现在 active 查询 | 通过 |
| 归档项目不改写会话自身归档选择 | 恢复后会话状态被错误重置 | ProjectRepository | service unit 与 integration | 项目归档恢复前后会话 status 不变 | unit 通过；integration 待 Linux PostgreSQL 执行 |
| 并发删除不能被归档操作复活 | deleted 会话重新变成 active/archived | Project/Conversation 行锁与状态迁移 | PostgreSQL integration | 删除持锁后并发归档最终保持 deleted | integration 已编写，待 Linux PostgreSQL 执行 |
| Schema 可从当前版本幂等升级 | 生产约束拒绝 archived | storage-migrator | schema migration integration | v8 约束升级后接受 archived | 测试已更新，待 Linux PostgreSQL 执行 |

## 后果

主列表查询必须同时尊重 Conversation 和 Project 生命周期。已归档入口使用独立加载状态，避免扩大常规侧栏首屏请求。归档资源仍占用持久存储，用户需要永久清理时继续使用删除功能。
