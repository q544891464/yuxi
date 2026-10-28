# Basic 同步模型 tokenizer 计数

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/agents/middlewares/summary.py

## 问题
近似字符计数不能准确表示中文、工具定义与聊天模板的实际输入，摘要可能过早触发。cydx 已有同源 vLLM tokenizer 能力，Basic 需要同步而保留自身资源授权、员工入口和未配置供应商的原行为。

## 决策
供应商 extra_json.context_tokenizer 显式声明 type=vllm、context_window；调用同源 /tokenize，返回的 max_model_len 必须等于声明窗口，不一致明确失败。摘要和主／子智能体最终请求预算使用同一计数器，取智能体预算配置与已核验模型窗口的较小值，保留16K输出。启用时摘要触发上限为输入预算90%。计数失败明确拒绝生成，不静默降级。

未启用供应商继续 Basic 原有近似计数和摘要阈值，不引入 cydx 的字节预算、税务技能或提前删除历史的策略变化。同步流式工具双表示及参数截断副本一致性，异步调用不阻塞事件循环。

## 替代方案
整体复制 cydx Context 和 Graph 会覆盖 Basic 的资源选择、共享配置及调用身份语义；本地 tokenizer 增加模型和模板版本同步职责。

## 后果
该能力只支持已核验聊天模板协议的 vLLM 服务，开启前必须核对模型窗口及实际 usage。未配置的供应商保持原行为，Basic 的资源选择、UID、重试、100K摘要阈值和员工入口保持原语义。配置方式由[上下文压缩机制](../../../mechanisms/context-compression.md#模型计数口径)拥有。此任务同步源码，不复制 cydx 供应商、凭据、业务数据或自动变更运行中实例。

## 验证
在 Linux ARM64 隔离容器中挂载 Basic 当前源码执行 `python -m pytest -p no:cacheprovider test/unit -m "not slow" -q`，2655项通过；`python -m unittest scripts.test_verify_engineering_contracts`，62项通过。容器禁用网络，无生产数据卷，使用现有运行镜像中的依赖；Basic锁定的 xlrd 2.0.2 额外以官方 wheel 加载并校验锁文件 SHA256。Linux快照保留Git执行位及shell LF。

负向测试覆盖计数超限不得到达handler、窗口错误／服务不可用不回退、未配置不调用计数、矛盾工具块拒绝、两条历史参数裁剪路径同步副本且原消息不变。摘要异步测试由真实计数器构造请求，响应通过 httpx.post mock 提供，并依赖异步ticker放行计数线程；摘要、历史保存与最终handler均执行。主子图测试验证预算器安装在提示注入后，摘要工厂保留Basic UID和会话。

相关文件 Ruff check、format --check、工程信任验证器及 diff检查通过，独立Reviewer复核通过。尚未部署Basic实例或执行真实模型HTTP／worker E2E，unit不作为该现场链路的通过证据。
