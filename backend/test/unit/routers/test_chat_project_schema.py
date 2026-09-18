import pytest
from pydantic import ValidationError

from server.routers.chat_router import ThreadCreate, ThreadUpdate


def test_thread_create_rejects_legacy_direct_workdir_path():
    """新线程只能通过 project_id 选择 Workdir。"""
    with pytest.raises(ValidationError):
        ThreadCreate(agent_id="main", workdir_path="client/demo")


def test_thread_update_accepts_project_move_request():
    """线程更新允许提交目标项目，权限和运行状态由服务层校验。"""
    update = ThreadUpdate(project_id="project-2")
    assert update.project_id == "project-2"
