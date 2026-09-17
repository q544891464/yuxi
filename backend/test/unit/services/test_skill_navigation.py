"""导航配置边界必须拒绝无法可靠展示的输入。"""

import pytest
from pydantic import ValidationError

from yuxi.services.skill_navigation_service import NavigationConfig


def node(id="one", **kwargs):
    """构造最小可调用入口。"""
    return dict(
        id=id,
        label="入口",
        skillSlug="sample-skill",
        skillDisplayName="技能",
        inputHint="材料",
        outputHint="结果",
        presetPrompt="处理材料",
        children=[],
        **kwargs,
    )


def test_valid_empty_and_nested_navigation():
    """空菜单及三级有序菜单都能保留。"""
    assert NavigationConfig(revision=0, nodes=[]).nodes == []
    root = node()
    root["children"] = [node("two")]
    assert NavigationConfig(revision=0, nodes=[root]).nodes[0].children[0].id == "two"


@pytest.mark.parametrize("defect", ["duplicate", "depth", "count", "blank", "slug", "extra", "revision"])
def test_invalid_navigation_rejected(defect):
    """非法结构或字段不能被发布。"""
    config = {"revision": 0, "nodes": [node()]}
    root = config["nodes"][0]
    if defect == "duplicate":
        root["children"] = [node()]
    elif defect == "depth":
        current = root
        for id in ["two", "three", "four"]:
            current["children"] = [node(id)]
            current = current["children"][0]
    elif defect == "count":
        config["nodes"] = [node(str(i)) for i in range(101)]
    elif defect == "blank":
        root["label"] = "  "
    elif defect == "slug":
        root["skillSlug"] = "../../etc"
    elif defect == "extra":
        root["script"] = "execute"
    else:
        config["revision"] = -1
    with pytest.raises(ValidationError):
        NavigationConfig.model_validate(config)
