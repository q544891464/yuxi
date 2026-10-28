from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from yuxi.agents.buildin.chatbot import graph as chatbot_graph
from yuxi.agents.buildin.subagent import graph as subagent_graph
from yuxi.agents.middlewares import summary as summary_module
from yuxi.agents.middlewares.context_budget import ContextBudgetMiddleware
from yuxi.models.context_tokenizer import VllmContextTokenizer
from yuxi.agents.context import filter_declared_config
from yuxi.agents.backends.composite import YuxiFilesystemMiddleware
from yuxi.agents.buildin.chatbot.prompt import TODO_MID_PROMPT
from deepagents.backends import CompositeBackend
from deepagents.backends.protocol import WriteResult
from langchain_core.messages import ToolMessage


def _context(summary_threshold: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        model="test-provider:test-model",
        summary_threshold=summary_threshold,
        summary_keep_messages=7,
        summary_prompt="SUMMARY {messages}",
        summary_tool_result_token_limit=300,
        tool_token_limit=3,
        model_retry_times=1,
        workdir_relative_path="projects/11111111-1111-4111-8111-111111111111",
        workdir_path="/home/gem/user-data/projects/11111111-1111-4111-8111-111111111111",
    )


def _patch_common_graph_deps(monkeypatch: pytest.MonkeyPatch, graph_module, captured: dict) -> None:
    monkeypatch.setattr(graph_module, "create_agent_filesystem_middleware", lambda *_args, **_kwargs: object())

    def create_summary_middleware_from_context(context, *, backend):
        captured["summary_context"] = context
        captured["summary_backend"] = backend
        return object()

    monkeypatch.setattr(
        graph_module,
        "create_summary_middleware_from_context",
        create_summary_middleware_from_context,
    )


@pytest.mark.parametrize(
    ("graph_module", "threshold", "build_args", "patch_subagent_task"),
    [
        (chatbot_graph, 123, (object(),), True),
        (subagent_graph, 64, (object(), "default"), False),
    ],
)
@pytest.mark.unit
@pytest.mark.asyncio
async def test_graph_uses_shared_summary_middleware_factory(
    monkeypatch: pytest.MonkeyPatch, graph_module, threshold: int, build_args, patch_subagent_task: bool
) -> None:
    captured: dict = {}
    _patch_common_graph_deps(monkeypatch, graph_module, captured)

    async def no_subagent_middleware(_context):
        return None

    if patch_subagent_task:
        monkeypatch.setattr(graph_module, "create_subagent_task_middleware", no_subagent_middleware)

    middlewares = await graph_module._build_middlewares(_context(summary_threshold=threshold), *build_args)

    assert captured["summary_context"].summary_threshold == threshold
    assert captured["summary_backend"] is build_args[0]
    middleware_names = [type(middleware).__name__ for middleware in middlewares]
    assert middleware_names.index("NetworkRetryMiddleware") < middleware_names.index(
        "ImageInputCompatibilityMiddleware"
    )
    todo = next(middleware for middleware in middlewares if type(middleware).__name__ == "TodoListMiddleware")
    assert todo.system_prompt == TODO_MID_PROMPT
    assert "首项立即标为 in_progress" in todo.system_prompt
    assert "先调用 write_todos" in todo.system_prompt
    assert "不要等所有核验结束后批量更新" in todo.system_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("graph_module", [chatbot_graph, subagent_graph])
@pytest.mark.parametrize("limit_k", [3, 16])
async def test_saved_tool_output_threshold_controls_main_and_subagent_eviction(monkeypatch, graph_module, limit_k):
    """实际配置穿过主子图，改变工具结果卸载并保留原文。"""

    class MemoryBackend:
        """记录本次隔离运行实际保存的完整工具输出。"""

        def __init__(self):
            self.files = {}

        def write(self, path, content):
            """保存正文并返回真实后端协议结果。"""
            self.files[path] = content
            return WriteResult(path=path)

    saved = filter_declared_config({"context": {"tool_token_limit": limit_k}})
    context = _context()
    context.tool_token_limit = saved["context"]["tool_token_limit"]
    memory = MemoryBackend()
    backend = CompositeBackend(default=memory, routes={}, artifacts_root=f"{context.workdir_path}/outputs")
    monkeypatch.setattr(graph_module, "create_summary_middleware_from_context", lambda *args, **kwargs: object())
    monkeypatch.setattr(graph_module, "create_context_budget_middleware", lambda _: None)
    if graph_module is chatbot_graph:
        monkeypatch.setattr(graph_module, "create_memory_middleware", AsyncMock(return_value=None))
        monkeypatch.setattr(graph_module, "create_subagent_task_middleware", AsyncMock(return_value=None))
        middlewares = await graph_module._build_middlewares(context, backend)
    else:
        middlewares = await graph_module._build_middlewares(context, backend, "default")
    filesystem = next(item for item in middlewares if isinstance(item, YuxiFilesystemMiddleware))
    content = "word " * 7000
    request = SimpleNamespace(tool_call={"name": "query_kb"}, runtime=SimpleNamespace())
    result = filesystem.wrap_tool_call(
        request, lambda _: ToolMessage(content=content, name="query_kb", tool_call_id="large-result")
    )
    if limit_k == 3:
        assert list(memory.files.values()) == [content]
        assert len(result.content) < len(content)
        assert "large_tool_results" in result.content
    else:
        assert memory.files == {}
        assert result.content == content


@pytest.mark.unit
def test_shared_summary_factory_uses_one_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def load_model(fully_specified_name, *, session_id, uid):
        """记录摘要模型实际接收的会话 ID 与用户 UID。"""
        captured["session_id"] = session_id
        captured["uid"] = uid
        return object()

    monkeypatch.setattr(summary_module, "load_chat_model", load_model)

    def create_summary_middleware(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(summary_module, "create_summary_middleware", create_summary_middleware)
    context = _context(summary_threshold=96)
    context.thread_id = "summary-thread"
    context.uid = "summary-uid"
    backend = object()

    summary_module.create_summary_middleware_from_context(context, backend=backend)

    assert captured["backend"] is backend
    assert captured["session_id"] == "summary-thread"
    assert captured["uid"] == "summary-uid"
    assert captured["trigger"] == ("tokens", 96 * 1024)
    assert captured["trim_tokens_to_summarize"] == 96 * 1024
    assert "l1_l2_trigger_ratio" not in captured
    assert captured["token_counter"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graph_module,build_args", [(chatbot_graph, (object(),)), (subagent_graph, (object(), "default"))]
)
async def test_enabled_tokenizer_is_installed_after_prompt_injection(monkeypatch, graph_module, build_args):
    """主子图都在所有注入器之后执行真实预算校验。"""
    _patch_common_graph_deps(monkeypatch, graph_module, {})
    if graph_module is chatbot_graph:
        monkeypatch.setattr(graph_module, "create_subagent_task_middleware", AsyncMock(return_value=None))
    info = SimpleNamespace(extra={"context_tokenizer": {"type": "vllm", "context_window": 131072}})
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    middlewares = await graph_module._build_middlewares(_context(), *build_args)
    assert isinstance(middlewares[-1], ContextBudgetMiddleware)
    assert middlewares[-1].input_budget == 114688


def test_enabled_summary_shares_real_tokenizer_and_window(monkeypatch):
    """摘要阈值遵守实际窗口，并保留 Basic 的用户与线程身份。"""
    captured = {}
    info = SimpleNamespace(extra={"context_tokenizer": {"type": "vllm", "context_window": 131072}})
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    monkeypatch.setattr(summary_module, "load_chat_model", lambda **kwargs: captured.update(kwargs) or object())
    monkeypatch.setattr(
        summary_module, "create_summary_middleware", lambda **kwargs: captured.update(kwargs) or object()
    )
    context = _context(summary_threshold=512)
    context.thread_id, context.uid = "thread-fixture", "user-fixture"
    summary_module.create_summary_middleware_from_context(context, backend=object())
    assert isinstance(captured["token_counter"], VllmContextTokenizer)
    assert captured["trigger"] == ("tokens", 103219)
    assert captured["session_id"] == context.thread_id
    assert captured["uid"] == context.uid


@pytest.mark.parametrize(
    "graph_module,agent_class",
    [
        (chatbot_graph, chatbot_graph.ChatbotAgent),
        (subagent_graph, subagent_graph.SubAgentBackend),
    ],
)
@pytest.mark.asyncio
async def test_graph_passes_conversation_session_to_model(monkeypatch, graph_module, agent_class):
    """主 Agent 与子 Agent 构图都使用实际线程的模型会话。"""
    context = _context()
    context.thread_id = "graph-thread"
    context.uid = "graph-uid"
    context._runtime_prepared = True
    monkeypatch.setattr(graph_module, "sync_agent_context_skills", AsyncMock())
    monkeypatch.setattr(graph_module, "resolve_configured_runtime_tools", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_module, "create_agent_composite_backend", lambda _context: object())
    monkeypatch.setattr(graph_module, "build_prompt_with_context", lambda _context: "test")
    monkeypatch.setattr(graph_module, "_build_middlewares", AsyncMock(return_value=[]))
    monkeypatch.setattr(agent_class, "_get_checkpointer", AsyncMock(return_value=None))
    captured = {}

    def load_model(fully_specified_name, *, session_id, uid):
        """用装配参数作为模型占位，核对传给图的对象。"""
        captured.update(spec=fully_specified_name, session_id=session_id, uid=uid)
        return captured

    monkeypatch.setattr(graph_module, "load_chat_model", load_model)
    monkeypatch.setattr(graph_module, "create_agent", lambda **kwargs: kwargs)
    graph = await agent_class().get_graph(context=context)
    assert graph["model"] == {"spec": context.model, "session_id": context.thread_id, "uid": context.uid}


@pytest.mark.parametrize("agent_class", [chatbot_graph.ChatbotAgent, subagent_graph.SubAgentBackend])
@pytest.mark.asyncio
async def test_graph_rejects_unprepared_context(agent_class):
    """未经权限资源准备的对象不能构建执行图。"""
    with pytest.raises(ValueError, match="已准备"):
        await agent_class().get_graph(context=_context())
