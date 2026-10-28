"""使用供应商服务端聊天模板计算上下文 token。"""

import json

import httpx
from langchain_core.messages import convert_to_openai_messages
from langchain_core.utils.function_calling import convert_to_openai_tool
from yuxi.utils import get_docker_safe_url


class VllmContextTokenizer:
    """显式启用的同源 vLLM 计数器；失败时拒绝继续调用模型。"""

    def __init__(self, info, window: int):
        """绑定本次运行的供应商与已声明模型窗口。"""
        self.info = info
        self.window = window

    def __call__(self, messages, *, tools=None, **kwargs) -> int:
        """计入聊天模板、工具定义、工具参数和生成提示。"""
        payload = {
            "model": self.info.model_id,
            "messages": convert_to_openai_messages(list(messages)),
            "add_generation_prompt": True,
        }
        for message in payload["messages"]:
            if message["role"] == "assistant" and isinstance(message.get("content"), list):
                # LangChain 流式消息同时在 content 与 tool_calls 表达调用；wire 只保留后者。
                calls = {call["id"]: call["function"] for call in message.get("tool_calls", [])}
                content = []
                for part in message["content"]:
                    if isinstance(part, dict) and part.get("type") == "tool_call":
                        call = calls.get(part.get("id"))
                        if (
                            not call
                            or call["name"] != part.get("name")
                            or json.loads(call["arguments"]) != part.get("args")
                        ):
                            raise ValueError("工具内容块与 wire tool_calls 不一致，拒绝丢弃输入")
                    else:
                        content.append(part)
                message["content"] = content or ""
        if tools:
            payload["tools"] = [convert_to_openai_tool(tool) for tool in tools]
        base_url = get_docker_safe_url(self.info.base_url)
        url = base_url.removesuffix("/").removesuffix("/v1") + "/tokenize"
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={**self.info.headers, "Authorization": f"Bearer {self.info.api_key}"},
                timeout=15,
                trust_env=False,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("模型 tokenizer 计数失败，未发送生成请求") from exc
        count = result.get("count")
        if type(count) is not int or count < 0 or result.get("max_model_len") != self.window:
            raise ValueError("模型 tokenizer 返回计数或窗口与供应商配置不符")
        return count
