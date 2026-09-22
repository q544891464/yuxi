# 技能导航的工作区可见范围

状态：implemented
类型：feature
Owner：backend/package/yuxi/services/skill_navigation_service.py

## 问题

角色范围无法区分同一用户在稽查、督查工作区中看到的技能入口，也无法单独隐藏子菜单。

## 决策

每个入口配置 visibleWorkspaces 和 childrenWorkspaces，取值 inspection / ducha，默认两个工作区以保留既有行为；空数组隐藏。父入口不可见则隐藏子树，下级范围与各子节点范围取交集。角色可见范围仍剪除整个子树。普通导航接口根据工作区返回过滤结果，并校验该用户的页面访问权限；管理接口保留完整配置。前端切换工作区立即清空旧菜单，隔离迟到响应。

本次配置将现有 case-dual 移为顶级入口，两工作区均可见，其下级仅督查可见；其他现有入口仅稽查可见。保留绑定、提示词和角色范围。当前 case-dual 无子节点，不创建虚构技能。

## 替代方案

仅按角色隐藏无法处理多工作区用户。仅在前端过滤会向无权限工作区返回隐藏的菜单和提示词。按页面复制完整菜单会重复维护同一技能配置。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 入口与下级分别按工作区过滤且不扩大角色权限 | 子树绕过父级或角色 | skill_navigation_service.py | unit 与真实 HTTP/PG | 禁止工作区及隐藏子节点不返回 | Passed：相关unit、真实HTTP/PG及浏览器验证 |
| 切换页面不显示旧菜单 | 迟到响应污染新工作区 | skillNavigation.js | store unit 与浏览器 | 逆序返回两个工作区响应 | Passed：相关unit、真实HTTP/PG及浏览器验证 |
| 管理员可持久化并回读设置 | 编辑丢失字段 | SkillNavigationSettings.vue | HTTP回读与浏览器编辑 | 非法值及普通用户保存被拒绝 | Passed：相关unit、真实HTTP/PG及浏览器验证 |

验证结果：导航真实HTTP/独立PostgreSQL与unit共17项通过；前端411项、后端2155项（排除slow）通过；ESLint、Ruff、前端构建、工程契约检查及62项契约测试、文档构建通过。浏览器本地隔离API fixture验证两区菜单与配置保存，截图覆盖两工作区和设置页。生产配置发布另行回读，不把fixture当成生产验证。

## 后果

这是菜单可见性，不授予技能执行权限，也不撤销已有技能共享权限。新增字段保存在既有配置JSON中，无数据库结构迁移。发布配置使用revision冲突检测。
