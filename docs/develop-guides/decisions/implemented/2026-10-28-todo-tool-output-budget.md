# Basic 同步阶段待办与工具结果阈值

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/context.py

## 问题
通用待办提示未明确阶段交接时更新，模型可能等任务结束后才批量更新。主子图已读取 tool_token_limit，但 Context 未声明该字段，管理员保存的值会被配置归一化过滤。

## 决策
同步 cydx 的通用待办提示：复杂任务先建3–5阶段、首项进行中、阶段交接先更新待办，实际交付后才标记完成。主、子图继续使用原 TodoListMiddleware，不改状态协议或引入强制规划机制。

声明管理员可配置的 tool_token_limit，沿用默认3K及现有主子图、文件后端和近似计量口径，不改变摘要工具预览阈值或整体 tokenizer 预算。仅同步这两项，不带入其他摘要、业务技能和部署调整。

### 实现方案
BaseContext 声明字段及管理员权限；既有配置过滤保留声明字段并限制用户写入，主、子图从各自Context读取阈值，换算为工具层近似token后传入FilesystemMiddleware，后者在工具返回时决定保留正文或保存完整正文并返回短结果。共享的 TODO_MID_PROMPT 由主、子图传给 TodoListMiddleware；模型调用 write_todos 后更新图状态，现有BaseAgent事件转换把状态交给消费者。本次不增加状态协议或规划执行器。

## 替代方案
只改前端不能使模型及时调用 write_todos；新增阶段状态机超出通用提示同步范围。直接改大所有工具输出阈值会改变默认内存和上下文行为。

## 后果
提示词提高阶段更新要求，不能保证任意模型一定及时更新。较高卸载阈值增加输入上下文，已启用的整体预算仍独立校验；已有文件工具分页及 open_kb_document 豁免不变。管理员配置方式见[智能体配置](../../../agents/agents-config.md)，执行与计量边界见[中间件](../../../agents/middleware.md)。本次只修改Basic源码并保存本地提交，不部署或调整现有员工配置。

## 验证
隔离Linux ARM64容器使用Basic源码执行 `python -m pytest -p no:cacheprovider test/unit -m "not slow" -q`，2660项通过；工程检查器unit 62项通过。相关135项包含配置权限、主子图实际文件中间件及真实图状态回归。容器禁用网络、不挂生产数据卷，沿用上一轮已核对的依赖及Basic锁定xlrd；源码快照保留Git执行位与shell LF。

阈值回归从已声明配置读取3K及16K，真实装配主子图并处理同一工具输出：3K写入完整正文并返回短结果，16K保留正文且不写卸载文件。权限回归验证普通用户不能修改或发现该管理员配置项，运行仍保留已保存配置。

待办回归使用生产 `TodoListMiddleware().tools`、ToolNode 和 StateGraph，构造确定工具调用；通过Basic显式Context与BaseAgent事件转换，等待下一工作节点开始后观察进行中待办，再释放阶段并验证完成状态。此测试使用内存checkpoint且不调用模型，不代表生产数据库、HTTP／worker链路或任意模型遵循提示词已验证。独立Reviewer复核通过；相关Ruff检查、文档构建、工程信任验证器与diff检查通过。
