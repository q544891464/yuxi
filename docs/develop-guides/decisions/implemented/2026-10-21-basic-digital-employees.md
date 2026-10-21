# Basic 数字员工广场与个人默认入口

状态：implemented
类型：feature
Owner：web/src/router/index.js

## 问题

Basic 已从 cydx 提取通用能力并吸收上游更新，原入口直接进入对话。管理员已有智能体资料、运行配置和共享权限编辑能力，普通用户缺少按用途选择数字员工的首页，也不能把默认入口保存在账号中。此次提供通用员工广场、配置入口及可切换的员工对话，保留通用知识库与技能能力。

## 决策

数字员工直接使用现有主 Agent 记录：名称、描述和形象由 Agent 资料拥有，知识库、技能和模型使用已有运行配置，访问范围复用 Agent read_scope。管理员在首页点击“配置数字员工”，进入原智能体编辑界面。子智能体不作为直接对话员工展示；系统助手保持原有全局可读语义。自建员工可按指定用户或部门共享，也可全局共享，知识库和技能的自身权限仍在执行时取交集；个人技能保持原有始终可用语义。

根路径按个人默认员工进入新对话，无有效默认值时展示广场；显式 /employees 始终打开广场。用户可以搜索、开始对话、保存或清除个人默认员工，聊天输入区也提供“员工广场”入口。已有对话继续沿用原智能体和会话路由。密码、分享和 OIDC 登录无显式目标时进入根路径，安全的显式目标继续保留。

个人默认员工由 UserConfig 拥有，使用 default_agent_id 保存主 Agent slug，业务 Schema 升至 13。字段更新只修改显式提供的值，避免 Memory 开关与默认员工互相覆盖。保存通过 AgentRepository 可见性校验；读取时对删除、撤权及非主员工目标返回空默认值。此处只投影失效值，不删除历史会话或重写其绑定。

头像上传与创建、保存存在竞态，可能提交空头像；现在提交等待在途上传完成，失败时不提交。手机使用图标侧栏及可展开的局部菜单，展开状态不写入桌面折叠偏好。

隔离验收还复现了内置技能首次初始化写入旧版共享结构，普通用户读取员工和技能返回 HTTP 500。修复位于技能初始化 Owner：新建内置技能写入 v2 ACL，更新继续使用现有 v2 路径；权限解析仍严格拒绝旧结构，不增加全局兼容回退。

## 替代方案

基于现有 basic 分支实施，保留其已吸收的上游升级与通用化结果。cydx 相比共同基线的新增提交为行业文案与离线交付记录，不重新复制进 Basic 产品。界面不预置税务名称、角色、流程、徽标或人物。

复制覆盖 cydx 工作树会丢失 Basic 的升级并重新引入行业功能；另建员工模型会复制 Agent 配置与授权；仅保存浏览器默认值无法跨设备生效。选择复用 Agent 与账号配置，不新增员工执行引擎、商城或业务工作流。本次不部署生产，不迁移生产业务数据。

## 验收标准

以下证据在独立临时 PostgreSQL、Redis、MinIO 和 API 容器中产生，不复用生产数据卷或网络。API 使用当前源代码及已缓存依赖镜像，关闭应用 lifespan；环境未启动模型、worker 和沙盒，不能用此次页面验证声称完整运行链已通过。

| 验收主张 | 语义 Owner | 实际证据及负向案例 | 结果 |
|---|---|---|---|
| 首页仅显示可见主员工，后端拒绝绕过 | AgentRepository / Agent 请求服务 | 真实 HTTP 列表与详情；不可见、子智能体、缺失目标不能设默认；直接创建不可见员工 Run 返回 404 | 通过 |
| 管理员修改资料、形象及能力 | Agent 编辑表单 / 配置写服务 | 浏览器创建员工并刷新显示名称、描述、头像；HTTP 关联知识库元数据与固定技能，SQL 回读配置；普通用户编辑共享员工返回 403 | 通过；未执行实际知识检索 |
| 默认员工保存在账号且局部更新不覆盖 | UserConfig / Schema migration | 真实 PostgreSQL v12→v13、重复迁移、保留 Memory；HTTP 写读及 SQL 读回；删除、撤权后默认失效；显式 null 清除 | 通过 |
| 广场、默认入口和员工切换可使用 | 路由 / EmployeeSquareView / AgentView | 两个独立浏览器上下文读取同一默认员工；根路径进入目标欢迎页；返回广场可选择另一员工；取消默认后根路径显示广场；路由 unit 保留显式目标 | 通过；无真实模型任务 E2E |
| 头像不因立即保存丢失 | AgentEditModal | 浏览器延迟上传响应后立即创建：上传完成才提交，刷新后图片已加载；上传失败时创建请求数为 0，弹窗仍打开 | 通过 |
| 窄屏与主题下可操作 | AppLayout / 员工广场样式 | 1920×1080、1280×720、768×1024、375×812 DOM 宽度及截图；手机卡片宽 287px，无横向溢出；两种桌面折叠偏好下菜单均从 y=66 到屏幕底、文字可见；折叠偏好下最近/已归档可达，点击真实空历史会话后浮层关闭，旋转回桌面恢复 56px 折叠栏；明暗主题、搜索空态、网络失败重试 | 通过 |
| 新内置技能权限可由普通用户读取 | init_builtin_skills / 权限解析器 | 首次初始化的真实 PG 记录回读 v2/global；普通用户 HTTP 默认员工与可用技能 200，新增探针技能可见；旧 v1 结构仍被 parser 拒绝 | 通过 |

## 验证

- Linux 隔离容器中默认员工相关 unit：91 passed。命令目标为 test/unit/config/test_user_config.py、test/unit/routers/test_user_config_router.py、test/unit/services/test_storage_migration.py、test/unit/services/test_agent_request_service.py、test/unit/repositories/test_agent_repository.py；调用 python -m pytest，使用当前源代码。
- Linux test/unit/agents：224 passed。内置技能初始化、更新和拒绝 legacy 权限的 focused unit：3 passed。
- 真实 PostgreSQL 的 test/integration/services/test_schema_migration_version.py：24 passed。
- test/integration/api/test_user_config_api.py 的 3 个用例通过真实 HTTP 与真实 PG 执行；本地验收适配器仅替换独立测试账号、HTTP client 和连接配置，避开无专用沙盒令牌的全局清理 fixture。实际调用 python -m pytest output/employee-verification/test_user_api.py -q。
- 知识库配置验收只插入隔离库的元数据，不连接向量服务；通过真实 Agent 更新接口绑定并 SQL 回读。技能初始化的 test/integration/services/test_builtin_discovery.py::test_builtin_init_creates_v2_acl_and_user_can_read_resources 通过安全隔离 wrapper 实际执行：1 passed in 3.61s。测试首次写入真实 PG、独立 session 回读、普通用户真实 HTTP 读取，最后只清理探针记录与目录。实际调用隔离容器 python -m pytest output/employee-verification/run_builtin_acl_isolated.py -q -p no:cacheprovider。
- 前端 lint 与生产 build 通过；最终 corepack pnpm test:unit：442 passed、0 failed。最后补充手机历史列表挂载及跳转收起后，相关 unit 8/8、lint 和生产 build 再次通过，真实浏览器点击空历史会话及旋转验收通过。之前一次 api_boundary 文件 worker 无断言堆栈退出；同文件复跑 14/14 及最终全量均通过，不据此归因环境或声称已修复该间歇退出。
- 工程契约检查通过；工程契约 unittest 在 Linux 62 项通过。Windows 同一 unittest 为 61 passed、1 error，原因是符号链接创建被系统权限拒绝，未将其伪装为代码通过。
- 文档生产构建通过（exit 0，40.06 秒）；链接及工程契约检查通过。最终 git diff --check 通过。
- 变更提交前由不继承实现上下文的独立 Reviewer 审查完整需求、diff 与验证范围。

浏览器验收可重做：在隔离环境创建一个全局只读员工并设置图片、知识库及技能；普通用户设为默认后在另一浏览器登录，检查目标欢迎页；返回员工广场切换、清除默认，检查根路径；延迟或拒绝上传响应后立即提交；切换明暗主题、四种屏幕尺寸、侧栏展开状态和搜索、失败重试。不得使用生产账号或业务材料。

## 后果

后端全量非 slow unit 未通过且不完整：收集 2605 项后，首次因只读投影目录退出；改用独立可写投影目录后仍在约 2% 无 pytest 汇总退出。随后 config、routers、services、repositories 集合至少观察到 test_sandbox_runtime_image 两项、test_shell_archive_line_endings 两项失败，并在约 67% 无汇总退出。原始终端输出没有保存，现有证据不足以给出根因，不声称全量通过。此范围仍需在标准完整测试拓扑中复核。

内置技能集成文件的标准 pytest fixture 会访问沙盒 provisioner；当前没有隔离沙盒令牌，因此通过安全 wrapper 执行新增用例的初始化与真实 HTTP 验证，不执行该文件的完整标准 fixture 集合、不调用生产 provisioner。真实模型回复、知识检索、worker/FIFO/SSE、沙盒文件产物及运行中切换的端到端验证未执行。手机历史跳转只验证空线程路由和菜单 DOM；该隔离库缺少 checkpoints 表，state 接口返回 500（日志为 psycopg.errors.UndefinedTable），history 返回 200 且消息为 0，因此不声称会话状态读取通过。

默认入口增加一次账号配置与可见员工读取；读取失败显示可重试广场。上线时需要执行现有启动迁移流程到业务 Schema 13，本次没有修改生产数据库。功能代码已落地，后端全量测试和真实模型链路限制保留在交付说明中。
