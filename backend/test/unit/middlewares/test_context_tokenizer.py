"""验证服务端 token 预算拒绝超限及计数协议错误。"""

from types import SimpleNamespace
from unittest.mock import Mock
import asyncio
import time

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from yuxi.agents.middlewares.context_budget import create_context_budget_middleware
from yuxi.models.context_tokenizer import VllmContextTokenizer
from yuxi.agents.middlewares.summary import YuxiSummarizationMiddleware
from langchain.agents.middleware.types import ModelRequest


@pytest.fixture
def info():
    """提供没有真实凭据的模型配置。"""
    return SimpleNamespace(
        model_id="test",
        base_url="http://model.test/v1",
        api_key="test-key",
        headers={},
        extra={"context_tokenizer": {"type": "vllm", "context_window": 131072}},
    )


def test_tokenizer_sends_chat_template_tools_and_tool_messages(monkeypatch, info):
    """工具参数和系统提示必须到达真实聊天模板边界。"""
    post = Mock(return_value=httpx.Response(200, json={"count": 90123, "max_model_len": 131072}))
    post.return_value.request = httpx.Request("POST", "http://model.test/tokenize")
    monkeypatch.setattr(httpx, "post", post)
    messages = [
        SystemMessage("规则"),
        HumanMessage("税" * 1000),
        AIMessage("", tool_calls=[{"id": "a", "name": "inspect", "args": {"text": "证据"}}]),
        ToolMessage("核验结果", tool_call_id="a"),
    ]
    tool = {"type": "function", "function": {"name": "inspect", "parameters": {"type": "object"}}}
    assert VllmContextTokenizer(info, 131072)(messages, tools=[tool]) == 90123
    payload = post.call_args.kwargs["json"]
    assert [m["role"] for m in payload["messages"]] == ["system", "user", "assistant", "tool"]
    assert payload["tools"][0]["function"]["name"] == "inspect"
    assert "证据" in payload["messages"][2]["tool_calls"][0]["function"]["arguments"]
    assert payload["add_generation_prompt"] is True


def test_tokenizer_uses_the_same_container_address_as_chat(monkeypatch, info):
    """容器内计数与生成必须指向同一供应商地址。"""
    monkeypatch.setattr(
        "yuxi.models.context_tokenizer.get_docker_safe_url", lambda url: "http://host.docker.internal:8000/v1"
    )
    response = httpx.Response(
        200,
        json={"count": 4, "max_model_len": 131072},
        request=httpx.Request("POST", "http://host.docker.internal:8000/tokenize"),
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(httpx, "post", post)
    VllmContextTokenizer(info, 131072)([HumanMessage("测试")])
    assert post.call_args.args[0] == "http://host.docker.internal:8000/tokenize"


def test_streamed_parallel_tool_calls_are_not_duplicated_in_content(monkeypatch, info):
    """真实流式双工具调用不能把内部 tool_call 块发到 vLLM content。"""
    calls = [
        {"id": "a", "name": "ls", "args": {"path": "/uploads"}},
        {"id": "b", "name": "ls", "args": {"path": "/skills"}},
    ]
    message = AIMessage(
        content=[{"type": "text", "text": "检查材料"}, *[{"type": "tool_call", **call} for call in calls]],
        tool_calls=calls,
    )
    response = httpx.Response(
        200, json={"count": 50, "max_model_len": 131072}, request=httpx.Request("POST", "http://model.test/tokenize")
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(httpx, "post", post)
    VllmContextTokenizer(info, 131072)(
        [HumanMessage("测试"), message, ToolMessage("[]", tool_call_id="a"), ToolMessage("[]", tool_call_id="b")]
    )
    wire = post.call_args.kwargs["json"]["messages"][1]
    assert wire["content"] == [{"type": "text", "text": "检查材料"}]
    assert [call["id"] for call in wire["tool_calls"]] == ["a", "b"]
    assert "/uploads" in wire["tool_calls"][0]["function"]["arguments"]
    assert "/skills" in wire["tool_calls"][1]["function"]["arguments"]


@pytest.mark.parametrize("wire_calls", [[], [{"id": "a", "name": "ls", "args": {"path": "/different"}}]])
def test_orphan_or_conflicting_content_tool_calls_are_rejected(monkeypatch, info, wire_calls):
    """没有对应表示或参数矛盾的工具块不能被静默删除。"""
    post = Mock()
    monkeypatch.setattr(httpx, "post", post)
    message = AIMessage(
        content=[{"type": "tool_call", "id": "a", "name": "ls", "args": {"path": "/uploads"}}], tool_calls=wire_calls
    )
    with pytest.raises(ValueError, match="拒绝丢弃输入"):
        VllmContextTokenizer(info, 131072)([HumanMessage("测试"), message])
    post.assert_not_called()


def test_tool_only_streamed_content_is_an_empty_string(monkeypatch, info):
    """纯工具调用的正文采用正常 OpenAI 空字符串表示。"""
    call = {"id": "a", "name": "ls", "args": {"path": "/uploads"}}
    message = AIMessage(content=[{"type": "tool_call", **call}], tool_calls=[call])
    response = httpx.Response(
        200, json={"count": 10, "max_model_len": 131072}, request=httpx.Request("POST", "http://model.test/tokenize")
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(httpx, "post", post)
    VllmContextTokenizer(info, 131072)([HumanMessage("测试"), message, ToolMessage("[]", tool_call_id="a")])
    assert post.call_args.kwargs["json"]["messages"][1]["content"] == ""


@pytest.mark.parametrize("phase", ["upstream", "compaction"])
def test_truncation_keeps_typed_blocks_and_wire_calls_consistent(monkeypatch, info, phase):
    """历史参数两条压缩路径都须同步副本，原 checkpoint 内容不能变。"""
    full_text = "事实与证据" * 1500
    call = {"id": "a", "name": "write_file", "args": {"file_path": "/report.md", "content": full_text}}
    original = AIMessage(content=[{"type": "tool_call", **call}], tool_calls=[call])
    messages = [HumanMessage("生成报告"), original, ToolMessage("ok", tool_call_id="a"), HumanMessage("继续")]
    middleware = object.__new__(YuxiSummarizationMiddleware)
    middleware.tool_arg_max_length = 100
    middleware.tool_result_offload_token_limit = 300
    middleware._max_arg_length = 100
    middleware._truncation_text = "...(argument truncated)"
    if phase == "upstream":
        monkeypatch.setattr(middleware, "_should_truncate_args", lambda *args: True)
        monkeypatch.setattr(middleware, "_determine_truncate_cutoff_index", lambda *args: 2)
        updated, _ = middleware._truncate_args(messages, 200000)
    else:
        updated = middleware._compact_messages(messages)
    assert updated[1].content[0]["args"] == updated[1].tool_calls[0]["args"]
    assert updated[1].tool_calls[0]["args"]["content"] != full_text
    assert original.content[0]["args"]["content"] == full_text
    assert original.tool_calls[0]["args"]["content"] == full_text
    response = httpx.Response(
        200, json={"count": 50, "max_model_len": 131072}, request=httpx.Request("POST", "http://model.test/tokenize")
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    assert VllmContextTokenizer(info, 131072)(updated) == 50


def test_budget_clamps_to_real_window_and_refuses_overflow(monkeypatch, info):
    """512K 旧配置不能绕过服务实际 128K 窗口。"""
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    budget = create_context_budget_middleware(SimpleNamespace(model="test:model", max_context_tokens=512))
    assert budget.input_budget == 114688
    budget.counter = lambda *args, **kwargs: 114689
    with pytest.raises(ValueError, match="114689 > 114688.*tokens"):
        budget.validate_messages([HumanMessage("测试")])


@pytest.mark.parametrize(
    "response",
    [
        {"count": -1, "max_model_len": 131072},
        {"count": 2, "max_model_len": 1048576},
        {"count": True, "max_model_len": 131072},
    ],
)
def test_invalid_tokenizer_response_is_rejected(monkeypatch, info, response):
    """失真的计数和错误窗口不能被当成成功。"""
    result = httpx.Response(200, json=response, request=httpx.Request("POST", "http://model.test/tokenize"))
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: result)
    with pytest.raises(ValueError, match="计数或窗口"):
        VllmContextTokenizer(info, 131072)([HumanMessage("测试")])


def test_tokenizer_unavailable_does_not_fall_back_to_bytes(monkeypatch, info):
    """计数失败不能悄悄恢复导致频繁摘要的旧字节估算。"""
    monkeypatch.setattr(httpx, "post", Mock(side_effect=httpx.ConnectError("offline")))
    with pytest.raises(RuntimeError, match="计数失败"):
        VllmContextTokenizer(info, 131072)([HumanMessage("测试")])


def test_unconfigured_provider_keeps_basic_legacy_budget(monkeypatch, info):
    """未显式启用的供应商不增加新拦截器，也不请求计数服务。"""
    info.extra = {}
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    post = Mock()
    monkeypatch.setattr(httpx, "post", post)
    assert create_context_budget_middleware(SimpleNamespace(model="test:model")) is None
    post.assert_not_called()


@pytest.mark.parametrize("settings", [[], {"type": "unknown"}, {"type": "vllm", "context_window": True}])
def test_invalid_provider_tokenizer_settings_fail_closed(monkeypatch, info, settings):
    """声明错误不能退回旧估算并继续生成。"""
    info.extra = {"context_tokenizer": settings}
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    with pytest.raises(ValueError, match="tokenizer"):
        create_context_budget_middleware(SimpleNamespace(model="test:model"))


@pytest.mark.asyncio
async def test_server_overflow_never_reaches_handler_and_does_not_block_loop(monkeypatch, info):
    """真实计数路径拒绝超限，同时其他异步任务能够继续运行。"""
    monkeypatch.setattr("yuxi.models.providers.cache.model_cache.get_model_info", lambda _: info)
    ticked = []

    def post(*args, **kwargs):
        time.sleep(0.1)
        return httpx.Response(
            200,
            json={"count": 114689, "max_model_len": 131072},
            request=httpx.Request("POST", "http://model.test/tokenize"),
        )

    async def tick():
        await asyncio.sleep(0.01)
        ticked.append(True)

    monkeypatch.setattr(httpx, "post", post)
    budget = create_context_budget_middleware(SimpleNamespace(model="test:model", max_context_tokens=512))
    request = ModelRequest(
        model=Mock(), messages=[HumanMessage("测试")], tools=[], runtime=Mock(), state={}, model_settings={}
    )
    handler = Mock()
    ticker = asyncio.create_task(tick())
    with pytest.raises(ValueError, match="114689 > 114688"):
        await budget.awrap_model_call(request, handler)
    assert ticked
    await ticker
    handler.assert_not_called()
