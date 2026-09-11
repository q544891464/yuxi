# 稽查报告解析技能入口

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/skills/buildin/__init__.py

## 问题

审理用户需要上传稽查报告并从聊天首页调用指定的结构化解析技能。

## 决策

用户提供的 Markdown 原文打包为内置 `tax-inspection-report-parser` Skill，复用 API 启动同步、共享权限和技能投影。原文仅作为运行时技能内容，不作为开发指令。ChatWelcome 展示解析卡片，AgentChatComponent 通过 welcome slot 传入当前智能体的可用技能；目标可用时生成现有 skill mention 格式的草稿。点击不自动发送，报告附件沿用原有输入区上传入口。所有变更保留本地，未部署。

## 替代方案

仅填入自然语言不能保证明确引用指定技能；另建解析 API 会复制现有文件与模型调用链路。单独修改线上数据库不符合本地完成的约束，且无法随源码交付。

## 后果

技能随内置技能同步流程安装，未初始化或当前智能体未启用时按钮禁用，不绕过后端资源授权。技能原文只提取事实和疑点，不生成最终审理结论。新增首页卡片不显示虚构统计。

## 验证

- 原始文件逐字节比对、frontmatter 与内置注册匹配检查通过。
- `node --test test/unit/report_parser_entry.test.js` 验证可用技能生成正确引用；目标不可用时按钮禁用且直接调用处理函数也不生成草稿。
- 真实浏览器组件预览验证卡片和点击后的草稿；可用技能数据使用本地测试 fixture，不代表后端数据库已安装。
- 本机缺少 Docker，未运行 PostgreSQL 安装、后端容器 unit、完整附件上传及真实模型解析。API 启动同步路径沿用现有实现；数据库安装状态和模型结果需在后续启动环境后验证。
