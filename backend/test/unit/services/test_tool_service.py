from __future__ import annotations

from types import SimpleNamespace

import pytest

from yuxi.agents.toolkits import service as tool_service


def test_get_tool_metadata_includes_config_guide(monkeypatch):
    tool_service._metadata_cache.clear()

    fake_tool = SimpleNamespace(
        name="demo_tool",
        description="demo description",
        metadata={},
        args_schema=None,
    )
    fake_extra = SimpleNamespace(
        category="buildin",
        tags=["demo"],
        display_name="演示工具",
        config_guide="请先配置 DEMO_API_KEY",
    )

    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_tool_instances",
        lambda: [fake_tool],
    )
    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_extra_metadata",
        lambda: {"demo_tool": fake_extra},
    )

    result = tool_service.get_tool_metadata()

    assert result == [
        {
            "slug": "demo_tool",
            "name": "演示工具",
            "description": "demo description",
            "metadata": {},
            "args": [],
            "category": "buildin",
            "tags": ["demo"],
            "config_guide": "请先配置 DEMO_API_KEY",
        }
    ]

    tool_service._metadata_cache.clear()


def test_metadata_cache_remains_empty_when_cold_load_fails(monkeypatch):
    """首次解析失败不能留下让后续请求误判为已加载的半缓存。"""
    tool_service._metadata_cache.clear()

    valid_tool = SimpleNamespace(
        name="valid_tool",
        description="valid",
        metadata={},
        args_schema=None,
    )

    class InvalidSchema:
        @classmethod
        def schema(cls):
            raise ValueError("invalid schema")

    invalid_tool = SimpleNamespace(
        name="invalid_tool",
        description="invalid",
        metadata={},
        args_schema=InvalidSchema,
    )
    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_tool_instances",
        lambda: [valid_tool, invalid_tool],
    )
    monkeypatch.setattr(
        "yuxi.agents.toolkits.registry.get_all_extra_metadata",
        lambda: {},
    )

    with pytest.raises(ValueError, match="invalid schema"):
        tool_service.get_tool_metadata()

    assert tool_service._metadata_cache == []


def test_extract_zip_schema_excludes_injected_runtime():
    """模型参数 Schema 只暴露文件路径，不序列化 ToolRuntime。"""
    from yuxi.agents.toolkits.buildin.tools import extract_zip

    schema = extract_zip.args_schema.model_json_schema()

    assert set(schema["properties"]) == {"file_path"}
    assert schema["required"] == ["file_path"]
