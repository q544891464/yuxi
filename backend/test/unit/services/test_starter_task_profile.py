"""首次任务示例必须匹配真实预置角色，不能仅凭名称推断。"""

import copy

import pytest

from yuxi.agents.presets.default_chatbot import PRESET as ASSISTANT
from yuxi.agents.presets.deep_research import PRESET as RESEARCH
from yuxi.services.agent_config_service import get_starter_task_profile


@pytest.mark.parametrize("preset", [ASSISTANT, RESEARCH])
def test_preset_profile_accepts_deployment_model_and_resource_selection(preset):
    """角色行为一致时允许部署模型与资源选择不同。"""
    agent = {
        "slug": preset.slug,
        "backend_id": preset.backend_id,
        "config_json": {"context": {**copy.deepcopy(preset.context), "model": "test/model", "skills": []}},
    }
    assert get_starter_task_profile(agent) == preset.slug


@pytest.mark.parametrize(
    "patch",
    [
        {"slug": "custom", "name": "智能助手"},
        {"backend_id": "SubAgentBackend"},
        {"is_subagent": True},
        {"config_json": {"context": {"system_prompt": "仅负责另一项工作"}}},
        {"config_json": {"context": {"preload_skills": ["custom-skill"]}}},
        {"config_json": {"context": {"max_execution_steps": 1}}},
    ],
)
def test_custom_or_changed_employee_has_no_preset_examples(patch):
    """同名自建、角色改写与行为配置变化均取消预置示例。"""
    agent = {"slug": ASSISTANT.slug, "backend_id": ASSISTANT.backend_id, "config_json": {"context": {}}}
    assert get_starter_task_profile({**agent, **patch}) is None


def test_research_requires_its_declared_role_prompt():
    """研究员工移除专属提示词后不得保留研究示例。"""
    agent = {"slug": RESEARCH.slug, "backend_id": RESEARCH.backend_id, "config_json": {"context": {}}}
    assert get_starter_task_profile(agent) is None
