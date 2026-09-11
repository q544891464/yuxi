# 稽查报告解析技能入口

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/buildin/__init__.py

## 问题

审理用户需要上传稽查报告并从聊天首页调用指定的结构化解析技能。

## 决策

用户提供的 Markdown 原文打包为内置 `tax-inspection-report-parser` Skill，复用 API 启动同步、共享权限和技能投影。原文仅作为运行时技能内容，不作为开发指令。ChatWelcome 展示解析卡片，AgentChatComponent 通过 welcome slot 传入当前智能体的可用技能；目标可用时生成现有 skill mention 格式的草稿。点击不自动发送，报告附件沿用原有输入区上传入口。

## 替代方案

仅填入自然语言不能保证明确引用指定技能；另建解析 API 会复制现有文件与模型调用链路。单独修改数据库无法随源码交付，也无法通过启动同步恢复。

## 后果

技能随内置技能同步流程安装，未初始化或当前智能体未启用时按钮禁用，不绕过后端资源授权。技能原文只提取事实和疑点，不生成最终审理结论。新增首页卡片不显示虚构统计。

## 验证

- 原始文件逐字节比对、frontmatter 与内置注册匹配检查通过。
- `node --test test/unit/report_parser_entry.test.js` 验证可用技能生成正确引用；目标不可用时按钮禁用且直接调用处理函数也不生成草稿。
- 真实浏览器：普通用户登录后首页入口可用，点击产生 Skill 引用草稿；上传虚构文本报告后发送成功。
- PostgreSQL 回读确认技能 enabled、builtin、全局共享；实际 Run 为 completed，同一 Run 的工具记录确认成功读取该 Skill，助手输出含案件编号、结构化 JSON、原文溯源、缺失项，以及测试材料 600.00 元和 650.00 元的冲突。
- 服务器技能 service、middleware、runtime 相关测试 90 项通过，工程契约及其 62 项单元测试通过。Word/PDF 解析和真实业务报告未逐项验证；文本附件验证不能替代这部分格式覆盖。
