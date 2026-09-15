# 用户首页知识问题与资源统计

状态：implemented
类型：feature
Owner：web/src/components/ChatWelcome.vue

## 问题

用户首页的问题与知识库检索测试脱节，资源数量未显示，输入区缺少参考图中的小人物。

## 决策

从已按用户权限过滤的知识库列表读取文件数与持久化示例问题，选择前四个去重问题填入输入框。子智能体与 Skills 复用各自可访问列表统计。加载失败展示未获取而非零；真实空列表显示零。使用用户提供的素材生成透明 PNG 人物，替换大图和小人物，在新对话输入框上方左侧添加不拦截点击的装饰，保持既有会话输入与历史布局。

## 替代方案

2026-09-15：用户要求已有对话也在输入框上沿显示人物。由 `AppLayout.vue` 为 `/chat` 保持 `minmax(0, 1fr) auto` 两行 Grid，消息区独立滚动。`AgentChatComponent.vue` 将装饰 slot 与实际输入区放入 `.composer-shell`，项目选择等额外控件留在 shell 外；人物脱离文档流，仅相对 shell 定位。不得用顶部留白或独立高度解决遮挡，否则会在页面底部产生大块空白。

把截图中的问题和数字写死无法随知识库内容及用户权限更新。新建聚合接口会重复已有访问权限及资源列表接口，因此仅补齐知识库可访问列表的两个摘要字段。

## 后果

2026-09-15 根据最新反馈，首页和正式对话均恢复两行 Grid，输入区位于底部；首页不渲染输入框人物。消息区首项通过 auto 顶部 margin 吸收短内容的剩余空间，底部 padding 为 8px，避免正文末尾与输入框之间出现大块空白；长内容仍在消息区滚动。正式对话人物 bottom 为 100%，取消以下旧版描述的 16px 压入，避免覆盖 placeholder。消费者页面高度继续由 AppLayout 的 100% 约束。

人物框固定为 150×157px，使用 `left: 18px` 与 `bottom: 100%` 贴在输入框左上沿，图片使用 contain 和 left bottom，并且人物框及图片均禁用 pointer events。`.composer-shell` 是人物唯一的定位父级，只保留 `position: relative` 与 `overflow: visible`；composerZone 不设置 mascot 专用 padding、margin、height 或 min-height，shell 高度等于实际输入区高度。为防止 1280px 宽度时正文列与人物水平重叠，消息列在 1360px 以下收窄并保持居中；素材 alpha 边界检查未发现巨大透明留白。

统计为列表读取时的快照，重新进入首页刷新。文件夹不计入文件数；外部只读知识库不以检索条目冒充文件数。新增摘要不开放任何管理权限，也不返回知识库密钥或原文。

## 验证

- 本次发布：前端完整单测 337/337、lint 与发布构建通过。工程契约检查通过；契约单测受 Windows symlink 权限和路径分隔符影响有两项未通过。生产容器后端单测在启动前因 editable 包目录时间戳权限失败，未执行测试；本次仅发布前端。

- 2026-09-15 最新布局：本地 Playwright 在 1280×720、1920×1080 回读首页输入区下沿分别为 720px、1080px；注入短消息的布局验证中，正文末尾距输入区为 8px。Lint 通过。API 与消息为模拟数据，未验证真实发送链路。

- 2026-09-15 定位上下文验证：Playwright DOM/CSS 回读确认 `.bottom.composer-zone` 的旧 `padding-top: 165px` 已移除；`composer-mascot` 的 offsetParent 为 `.composer-shell`，人物为 150×157px。项目选择器显示与脚本隐藏前后相对偏移不变；`.bottom` 和 `.composer-shell` 为 visible，其余页面祖先恢复原有 overflow 限制。此证据仅覆盖布局，未连接真实会话后端。

- 隔离 Linux 容器 `python -m pytest test/unit -m "not slow" -q`：2015 passed；新增普通用户私有知识库隔离案例后，相关 `test_file_listing_scaling.py` 11 passed。使用真实权限解析，私有库的文件数与问题不进入可见摘要。
- 服务器以真实 HTTP 调用修改后的知识库可访问列表及真实 PostgreSQL：未登录 401，管理员 200；返回文件数与文件表排除文件夹后的 count 一致。生产无普通用户账号，未创建或修改生产用户；普通用户隔离由上述 manager 测试证明，不声明普通用户完整 HTTP 验证通过。
- 前端 `pnpm run lint:check`、`pnpm run test:unit`（335 passed）、`pnpm run build` 通过。新案例验证去重四问、排除主智能体、文件夹不计数、零资源、失败、统计字段缺失。
- Playwright 检查 1600×1000、1366×768 页面，问题点击只填入草稿；低高度下问题不被底部人物遮挡。模拟知识库请求 503 显示未知并可重试，空响应显示零和空问题提示。页面知识库响应来自上述真实 HTTP，其余资源复用现有 API。
- 主图使用主形象的透明 PNG；输入框上方使用独立的标准正面透明 PNG。主形象由内置 imagegen 提取；标准正面按用户确认使用本地抠图，保留原人物像素并去除背景、标签与其他人物。原素材保留。
- Linux `python -m unittest scripts.test_verify_engineering_contracts`：62 tests 通过。
- 复审补充空 HTTP 响应体边界：null/undefined 不阻塞加载状态，5 项首页 utility 测试通过。
