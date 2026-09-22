# 会话查询测试建立所属项目

状态：implemented
类型：testing
Owner：backend/test/unit/storage/test_conversation_repository.py

## 问题

归档功能的列表与搜索查询只展示 active 项目中的会话。五项旧查询测试只插入会话和 project_id，未创建项目行，结果全部被正确过滤，无法再验证原有排序、分页和来源隔离。

## 决策

在这些查询测试中显式建立与会话所有者一致的 active 项目，保留原断言。增加 archived/deleted 项目会话不出现在列表和搜索的负向案例，不修改运行时查询。

## 替代方案

移除生产项目过滤会让归档内容重新出现在普通列表；放宽结果断言为空会失去原有分页与隔离验证。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 查询样本有合法项目关系，原排序与隔离仍被验证 | 旧夹具缺失关联 | test_conversation_repository.py | 会话 repository 单元测试 | archived/deleted 项目不进入普通列表及搜索 | Passed |

## 后果

只修正现有 SQLite 单元夹具，不把其结果视为 PostgreSQL 生命周期集成证据；归档 API 的集成测试保持独立。

完整后端 unit（not slow）在隔离 Linux 环境中 2152 项通过，未加载诊断插件或跳过失败测试。原有五项查询断言保留；新增两种非 active 项目负向案例。
