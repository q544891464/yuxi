# 首次对话工具元数据加载原子化

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/agents/toolkits/service.py

## 问题

新 Worker 第一次处理对话时会惰性加载全部工具元数据。`extract_zip` 依赖 LangGraph 注入的 `ToolRuntime`，此前未声明显式输入模型，Pydantic 为该运行时对象生成 JSON Schema 时遇到 `Callable` 而失败。加载器同时把已解析项目直接追加到全局缓存，异常后留下非空半缓存；下一次请求因此跳过加载并继续运行，形成“首次无响应，再发送一次才开始”的不稳定行为。

## 决策

`extract_zip` 使用显式 `ExtractZipInput`，只向模型公开 `file_path`，运行时注入对象不进入参数 Schema。工具元数据先构建到局部列表，全部成功后再一次性发布到进程缓存；任一工具失败时缓存保持空值，后续调用不会把不完整数据当成成功事实。

工具参数 Schema 由 `backend/package/yuxi/agents/toolkits/buildin/tools.py` 拥有；缓存发布语义由 `backend/package/yuxi/agents/toolkits/service.py` 拥有。

## 替代方案

在运行清单处捕获 Schema 异常会把错误工具继续暴露给模型，也无法修复其他工具元数据消费者。仅清空异常后的缓存仍会让所有首次请求失败。显式定义模型可见参数并原子发布缓存，直接修复两个真实缺陷且不改变工具执行接口。

## 后果

新进程的第一次对话与后续对话使用同一套完整工具元数据。以后若新增工具包含不可生成 Schema 的参数，首次加载会稳定失败并保持可重试状态，不会静默进入半加载状态。

## 验证

- `uv run ruff check package/yuxi/agents/toolkits/buildin/tools.py package/yuxi/agents/toolkits/service.py test/unit/services/test_tool_service.py`：通过。
- 生产同版本 Linux API 镜像隔离挂载修改后源码执行 `pytest /tmp/test_tool_service.py -q`：3 项通过；`extract_zip.args_schema.model_json_schema()` 只包含必填 `file_path`，并恢复“第二个工具解析失败”缺陷，断言全局缓存仍为空。
- 在生产同版本 API 镜像的独立容器中冷启动工具元数据，完整加载 13 个工具；随后针对此前 `manifest_persist_failed` 的 Run 构建 manifest 成功。
