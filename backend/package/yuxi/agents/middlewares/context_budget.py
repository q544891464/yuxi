"""显式启用 tokenizer 的模型请求预算。"""

import asyncio

from langchain.agents.middleware import AgentMiddleware

from yuxi.agents.context import DEFAULT_MAX_CONTEXT_K
from yuxi.models.context_tokenizer import VllmContextTokenizer

AGENT_OUTPUT_TOKENS = 16 * 1024


def create_context_budget_middleware(context):
    """按供应商声明启用真实计数，未配置时保留原模型调用。"""
    from yuxi.models.providers.cache import model_cache

    model_spec = getattr(context, "model", None)
    info = model_cache.get_model_info(model_spec) if isinstance(model_spec, str) and model_spec else None
    settings = info.extra.get("context_tokenizer") if info else None
    if settings is None:
        return None
    if not isinstance(settings, dict) or settings.get("type") != "vllm":
        raise ValueError("不支持的模型 tokenizer 类型")
    window = settings.get("context_window")
    if type(window) is not int or window <= AGENT_OUTPUT_TOKENS:
        raise ValueError("模型 tokenizer 窗口必须大于输出预留量")
    budget_k = getattr(context, "max_context_tokens", DEFAULT_MAX_CONTEXT_K)
    if type(budget_k) is not int or budget_k <= 16:
        raise ValueError("智能体上下文预算必须是大于 16 的整数 K")
    return ContextBudgetMiddleware(
        VllmContextTokenizer(info, window), min(budget_k * 1024, window) - AGENT_OUTPUT_TOKENS
    )


class ContextBudgetMiddleware(AgentMiddleware):
    """在所有提示注入后限制真实输入与输出，不修改消息正文。"""

    def __init__(self, counter, input_budget):
        """绑定当前运行使用的计数器和输入上限。"""
        self.counter = counter
        self.input_budget = input_budget

    def validate_messages(self, messages, *, tools=None):
        """超限输入不能到达生成接口。"""
        size = self.counter(messages, tools=tools)
        if size > self.input_budget:
            raise ValueError(f"智能体上下文超过输入预算：{size} > {self.input_budget} (tokens)；请分段读取材料后重试")

    def wrap_model_call(self, request, handler):
        """同步计数后执行生成。"""
        return handler(self._bounded_request(request))

    async def awrap_model_call(self, request, handler):
        """在线程中完成计数，保持事件循环可用。"""
        bounded = await asyncio.to_thread(self._bounded_request, request)
        return await handler(bounded)

    def _bounded_request(self, request):
        """完整校验最终输入并保留输出空间。"""
        messages = [request.system_message, *request.messages] if request.system_message else request.messages
        self.validate_messages(messages, tools=request.tools)
        settings = dict(request.model_settings)
        settings["max_tokens"] = min(settings.get("max_tokens") or AGENT_OUTPUT_TOKENS, AGENT_OUTPUT_TOKENS)
        return request.override(model_settings=settings)
