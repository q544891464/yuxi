# 通用数字员工沿用消费端聊天布局

状态：implemented
类型：feature
Owner：web/src/layouts/AppLayout.vue

## 问题

Basic 的员工广场和通用导航与 cydx 的聊天界面不同，品牌仍包含旧默认名称，员工形象没有进入欢迎区和输入框装饰。用户需要在通用产品中保留熟悉的聊天布局与左侧工作入口。

## 决策

### 实现方案

`AppLayout` 沿用 cydx 的顶栏、搜索、新建对话及项目后功能分组；技能菜单读取现有可访问 Skills 接口。“添加技能”沿用 `create-personal-skill` 虚拟意图，在可访问且被员工启用时引用真实 `skill-creator-v2`；缺失或未启用时明确提示，不伪造引用。根入口按个人默认员工进入 `/chat`，显式员工选择页仍可切换和设置默认员工。知识库与管理员数据总览作为消费端子路由显示，后端资源授权保持不变。

`ChatWelcome` 在首页使用当前员工名称、描述和已持久化的 `Agent.icon` 展示大人物；管理员上传入口明确该图片的使用位置。正式会话的输入框上沿显示小人物，首页不重复显示第二个人物。三款 GPT Image 卡通 PNG 随应用发布，作为未上传时的默认值和管理员可选形象；选择默认形象与上传一样写入现有 `icon` 保存流程。`AgentChatComponent` 仅新增真实输入框 `.composer-shell` 内的装饰插槽和草稿预填入口，运行、队列及附件 Owner 不变。人物绝对定位且不占垂直布局，窄屏隐藏输入框装饰，正文横向避让其所在的左侧范围。

默认品牌与旧默认名称归一化为“智能数字员工平台”，替换通用 Logo。内部 Python 包、API 和存储命名保留，现有自定义组织品牌不删除。不部署、不迁移业务资料、不恢复税务技能树或税务专属流程。

## 替代方案

直接复制 cydx 全部前端会引入税务接口和过期运行链路，且无法沿用通用员工权限。继续以员工广场作为根首页不能满足用户要求的既有聊天体验。新增独立人物字段会重复已有上传和持久化路径，当前单图需求复用 `Agent.icon`。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 默认可见品牌无 Yuxi 文案与原 Logo | 旧配置透出品牌 | platformBranding、info store | 品牌 unit、浏览器 DOM | 旧默认名称输入 | Passed |
| 左侧保留项目、员工选择、技能、知识库及管理员总览 | 入口消失或请求税务接口 | AppLayout、AccessibleSkillMenu | 组件 unit、浏览器 | 普通用户无管理员入口 | Passed |
| 人物相对于输入框定位且不覆盖正文 | 错误 offsetParent 或纵向占位 | AgentChatComponent、AgentView | 浏览器 bounding box、响应式截图 | 长正文、项目选择显隐、窄屏 | Passed |
| 技能选择预填真实引用且保留草稿 | 仅显示名称未提供引用 | AgentView、AgentChatComponent | 草稿 unit、浏览器 input DOM | 无权限或不存在的 slug | Passed |

## 后果

可见性仍由既有后端授权，前端隐藏不是安全边界。测试使用隔离页面数据，不修改生产员工、默认入口或业务资料。真实模型尚未配置，不将界面验证写成问答链路通过。

验证命令：`pnpm run lint:check`、`pnpm run test:unit`（452 项通过；随后默认 PNG、形象选择和技能启用限制的相关单测 9 项通过）、`pnpm run build`、`python scripts/verify_engineering_contracts.py`。工程契约单测在 Windows 受符号链接权限限制；相同源码在隔离 Linux 临时目录执行 `python3 -m unittest scripts.test_verify_engineering_contracts`，62 项通过。文档使用既有 VitePress 入口构建通过。

Chrome 以隔离 API 页面数据验证 1280×720、1920×1080、375×812、深色主题、技能预填、消费端知识库和默认人物弹窗；DOM 回读证明人物 offsetParent 为 composer-shell、宽高 150px、wrapper 高度等于输入框且长正文不与人物水平重叠。页面 fixture 不证明真实模型或后端运行链路。后端全量 unit 未执行：本机未提供 Docker 命令；本次不改变后端业务逻辑，仅更新默认品牌 YAML。未修改或部署生产环境。
