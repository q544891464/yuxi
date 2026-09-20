"""
Conversation thread status mapping and viewed-marking unit tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.repositories.conversation_repository import ConversationRepository, UNVIEWED_RUN_MARKER
from yuxi.services import conversation_service as svc
from yuxi.storage.postgres.models_business import AgentRun, Base, Conversation, Project

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_conversation(
    db,
    *,
    thread_id: str,
    last_viewed_run_id: str | None = None,
    conversation_status: str = "active",
    project_status: str = "active",
) -> Conversation:
    project_id = f"project-{thread_id}"
    db.add(
        Project(
            id=project_id,
            uid="user-1",
            selection_status="implicit",
            workdir_path=f"projects/workdir-{thread_id}",
            directory_mode="managed",
            status=project_status,
        )
    )
    conversation = Conversation(
        thread_id=thread_id,
        project_id=project_id,
        uid="user-1",
        agent_id="main",
        title=f"conv-{thread_id}",
        status=conversation_status,
        extra_metadata={},
        last_viewed_run_id=last_viewed_run_id,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _seed_run(db, *, thread_id: str, run_id: str, status: str, run_type: str = "chat") -> AgentRun:
    run = AgentRun(
        id=run_id,
        conversation_thread_id=thread_id,
        runtime_scope_id=thread_id,
        agent_slug="main",
        uid="user-1",
        status=status,
        request_id=f"req-{run_id}",
        run_type=run_type,
        created_by_run_id="root-run" if run_type == "subagent" else None,
        subagent_thread_relation_id=1 if run_type == "subagent" else None,
        input_payload={},
    )
    db.add(run)
    await db.flush()
    return run


@pytest.mark.parametrize(
    ("run_id", "run_status", "last_viewed_run_id", "expected"),
    [
        (None, None, None, "done"),
        ("r1", "running", None, "loading"),
        ("r1", "pending", None, "loading"),
        ("r1", "cancel_requested", None, "loading"),
        ("r1", "completed", None, "ready"),
        ("r1", "completed", "r1", "done"),
        ("r1", "failed", None, "ready"),
        ("r1", "cancelled", None, "ready"),
        ("r1", "interrupted", None, "ready"),
        ("r1", "interrupted", "r1", "done"),
    ],
)
async def test_thread_status_mapping(run_id, run_status, last_viewed_run_id, expected):
    assert svc._thread_status(run_id, run_status, last_viewed_run_id) == expected


async def test_list_threads_view_maps_run_states(session):
    await _seed_conversation(session, thread_id="thread-running")
    await _seed_run(session, thread_id="thread-running", run_id="run-running", status="running")

    await _seed_conversation(session, thread_id="thread-ready")
    await _seed_run(session, thread_id="thread-ready", run_id="run-ready", status="completed")

    await _seed_conversation(session, thread_id="thread-done", last_viewed_run_id="run-done")
    await _seed_run(session, thread_id="thread-done", run_id="run-done", status="completed")

    await _seed_conversation(session, thread_id="thread-no-run")
    await session.commit()

    items = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    status_by_id = {item["id"]: item["thread_status"] for item in items}

    assert status_by_id["thread-running"] == "loading"
    assert status_by_id["thread-ready"] == "ready"
    assert status_by_id["thread-done"] == "done"
    assert status_by_id["thread-no-run"] == "done"


async def test_archived_threads_are_separate_and_archived_projects_only_hide_active_threads(session):
    await _seed_conversation(session, thread_id="thread-active")
    await _seed_conversation(session, thread_id="thread-archived", conversation_status="archived")
    await _seed_conversation(
        session,
        thread_id="thread-in-archived-project",
        project_status="archived",
    )
    await _seed_conversation(
        session,
        thread_id="thread-archived-in-archived-project",
        conversation_status="archived",
        project_status="archived",
    )
    await session.commit()

    active = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    archived = await svc.list_threads_view(
        db=session,
        current_uid="user-1",
        agent_slug=None,
        limit=100,
        status="archived",
    )

    assert {item["id"] for item in active} == {"thread-active"}
    assert {item["id"] for item in archived} == {
        "thread-archived",
        "thread-archived-in-archived-project",
    }


async def test_archive_and_restore_thread_unpins_it(session):
    conversation = await _seed_conversation(session, thread_id="thread-archive")
    conversation.is_pinned = True
    await session.commit()

    archived = await svc.set_thread_archive_view(
        thread_id="thread-archive",
        archived=True,
        db=session,
        current_uid="user-1",
    )
    assert archived["id"] == "thread-archive"
    assert conversation.status == "archived"
    assert conversation.is_pinned is False

    restored = await svc.set_thread_archive_view(
        thread_id="thread-archive",
        archived=False,
        db=session,
        current_uid="user-1",
    )
    assert restored["id"] == "thread-archive"
    assert conversation.status == "active"


async def test_restore_thread_requires_active_project(session):
    await _seed_conversation(
        session,
        thread_id="thread-hidden",
        conversation_status="archived",
        project_status="archived",
    )
    await session.commit()

    with pytest.raises(svc.HTTPException) as exc:
        await svc.set_thread_archive_view(
            thread_id="thread-hidden",
            archived=False,
            db=session,
            current_uid="user-1",
        )

    assert exc.value.status_code == 409


async def test_list_threads_view_uses_joined_projects_without_per_thread_lookup(session, monkeypatch):
    """线程列表批量联查 Project，不按 Conversation 逐条解析。"""

    await _seed_conversation(session, thread_id="thread-one")
    await _seed_conversation(session, thread_id="thread-two")
    await session.commit()

    async def reject_individual_lookup(**_kwargs):
        raise AssertionError("线程列表不应逐条查询 Project")

    monkeypatch.setattr(svc, "resolve_conversation_workdir_path", reject_individual_lookup)

    items = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)

    assert {item["id"] for item in items} == {"thread-one", "thread-two"}


async def test_list_threads_view_ignores_subagent_and_other_users(session):
    await _seed_conversation(session, thread_id="thread-main")
    await _seed_run(session, thread_id="thread-main", run_id="run-main", status="completed")
    await _seed_run(session, thread_id="thread-main", run_id="run-sub", status="running", run_type="subagent")
    await _seed_conversation(session, thread_id="thread-other-user")
    db = session
    db.add(
        AgentRun(
            id="run-other",
            conversation_thread_id="thread-other-user",
            runtime_scope_id="thread-other-user",
            agent_slug="main",
            uid="user-2",
            status="running",
            request_id="req-other",
            run_type="chat",
            input_payload={},
        )
    )
    await db.commit()

    items = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    status_by_id = {item["id"]: item["thread_status"] for item in items}

    assert status_by_id["thread-main"] == "ready"
    assert status_by_id["thread-other-user"] == "done"


async def test_latest_run_wins_when_multiple_runs_exist(session):
    await _seed_conversation(session, thread_id="thread-latest", last_viewed_run_id="run-old")
    await _seed_run(session, thread_id="thread-latest", run_id="run-old", status="completed")
    await _seed_run(session, thread_id="thread-latest", run_id="run-new", status="completed")
    await session.commit()

    items = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    item = next(item for item in items if item["id"] == "thread-latest")

    assert item["thread_status"] == "ready"


async def test_mark_thread_viewed_turns_ready_to_done(session):
    await _seed_conversation(session, thread_id="thread-view")
    await _seed_run(session, thread_id="thread-view", run_id="run-view", status="completed")
    await session.commit()

    before = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    assert next(item for item in before if item["id"] == "thread-view")["thread_status"] == "ready"

    result = await svc.mark_thread_viewed_view(db=session, thread_id="thread-view", current_uid="user-1")
    assert result["thread_status"] == "done"

    after = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    assert next(item for item in after if item["id"] == "thread-view")["thread_status"] == "done"


async def test_mark_thread_viewed_keeps_loading_when_run_active(session):
    await _seed_conversation(session, thread_id="thread-active")
    await _seed_run(session, thread_id="thread-active", run_id="run-active", status="running")
    await session.commit()

    result = await svc.mark_thread_viewed_view(db=session, thread_id="thread-active", current_uid="user-1")

    assert result["thread_status"] == "loading"


async def test_new_thread_creation_uses_unviewed_marker(session):
    conversation = await ConversationRepository(session).add_conversation(
        uid="user-1",
        agent_id="main",
        title="new-thread",
        thread_id="thread-new",
        project_id="11111111-1111-4111-8111-111111111111",
    )

    assert conversation.last_viewed_run_id == UNVIEWED_RUN_MARKER


async def test_new_thread_creation_cannot_seed_attachment_records(session):
    conversation = await ConversationRepository(session).add_conversation(
        uid="user-1",
        agent_id="main",
        thread_id="thread-reserved-metadata",
        metadata={"attachments": [{"bucket_name": "private", "object_name": "secret"}]},
        project_id="22222222-2222-4222-8222-222222222222",
    )

    assert conversation.extra_metadata["attachments"] == []


async def test_create_thread_view_rejects_client_attachment_metadata():
    with pytest.raises(svc.HTTPException, match="服务端保留字段"):
        await svc.create_thread_view(
            agent_slug="main",
            request_id=None,
            title="malicious",
            metadata={"attachments": [{"bucket_name": "private", "object_name": "secret"}]},
            db=None,
            current_uid="user-1",
        )


async def test_update_thread_view_moves_conversation_to_owned_project(monkeypatch):
    conversation = SimpleNamespace(
        id=1,
        thread_id="thread-move",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
        last_viewed_run_id=None,
    )
    target_project = SimpleNamespace(id="project-new", workdir_path="projects/new")

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def lock_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def update_conversation(self, _thread_id, **_kwargs):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, project_id, uid):
            assert project_id == "project-new"
            assert uid == "user-1"
            return target_project

    class FakeAgentRunRepository:
        def __init__(self, _db):
            pass

        async def get_active_run_by_thread_for_user(self, **_kwargs):
            return None

        async def get_latest_top_level_runs_for_threads(self, _uid, _thread_ids):
            return {}

    class FakeAgentRunRequestRepository:
        def __init__(self, _db):
            pass

        async def list_queued(self, **_kwargs):
            return []

    class FakeSubagentThreadRepository:
        def __init__(self, _db):
            pass

        async def get_by_child_conversation_for_user(self, _conversation_id, _uid):
            return None

        async def get_by_parent_conversation_for_user(self, _conversation_id, _uid):
            return None

    async def serialize_thread(thread, **_kwargs):
        return {"id": thread.thread_id, "project_id": thread.project_id}

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(svc, "AgentRunRepository", FakeAgentRunRepository)
    monkeypatch.setattr(svc, "AgentRunRequestRepository", FakeAgentRunRequestRepository)
    monkeypatch.setattr(svc, "SubagentThreadRepository", FakeSubagentThreadRepository)
    monkeypatch.setattr(svc, "_serialize_thread", serialize_thread)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)

    result = await svc.update_thread_view(
        thread_id="thread-move",
        project_id="project-new",
        db=object(),
        current_uid="user-1",
    )

    assert conversation.project_id == "project-new"
    assert result == {"id": "thread-move", "project_id": "project-new"}


async def test_update_thread_view_rejects_move_while_run_is_active(monkeypatch):
    conversation = SimpleNamespace(
        thread_id="thread-busy",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def lock_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return SimpleNamespace(id="project-new", workdir_path="projects/new")

    class FakeAgentRunRepository:
        def __init__(self, _db):
            pass

        async def get_active_run_by_thread_for_user(self, **_kwargs):
            return SimpleNamespace(id="run-active")

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(svc, "AgentRunRepository", FakeAgentRunRepository)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-busy",
            project_id="project-new",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 409
    assert conversation.project_id == "project-old"


async def test_update_thread_view_rejects_move_with_queued_request(monkeypatch):
    conversation = SimpleNamespace(
        thread_id="thread-queued",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def lock_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return SimpleNamespace(id="project-new", workdir_path="projects/new")

    class FakeAgentRunRepository:
        def __init__(self, _db):
            pass

        async def get_active_run_by_thread_for_user(self, **_kwargs):
            return None

    class FakeAgentRunRequestRepository:
        def __init__(self, _db):
            pass

        async def list_queued(self, **_kwargs):
            return [SimpleNamespace(request_id="request-queued")]

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(svc, "AgentRunRepository", FakeAgentRunRepository)
    monkeypatch.setattr(svc, "AgentRunRequestRepository", FakeAgentRunRequestRepository)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-queued",
            project_id="project-new",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 409
    assert conversation.project_id == "project-old"


async def test_update_thread_view_rejects_move_with_subagent_threads(monkeypatch):
    conversation = SimpleNamespace(
        id=10,
        thread_id="thread-subagent",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def lock_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return SimpleNamespace(id="project-new", workdir_path="projects/new")

    class FakeAgentRunRepository:
        def __init__(self, _db):
            pass

        async def get_active_run_by_thread_for_user(self, **_kwargs):
            return None

    class FakeAgentRunRequestRepository:
        def __init__(self, _db):
            pass

        async def list_queued(self, **_kwargs):
            return []

    class FakeSubagentThreadRepository:
        def __init__(self, _db):
            pass

        async def get_by_child_conversation_for_user(self, _conversation_id, _uid):
            return None

        async def get_by_parent_conversation_for_user(self, _conversation_id, _uid):
            return SimpleNamespace(id=99)

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(svc, "AgentRunRepository", FakeAgentRunRepository)
    monkeypatch.setattr(svc, "AgentRunRequestRepository", FakeAgentRunRequestRepository)
    monkeypatch.setattr(svc, "SubagentThreadRepository", FakeSubagentThreadRepository)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-subagent",
            project_id="project-new",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 409
    assert conversation.project_id == "project-old"


async def test_update_thread_view_rejects_move_of_subagent_child_thread(monkeypatch):
    conversation = SimpleNamespace(
        id=11,
        thread_id="thread-child",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="subagent",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

        async def lock_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return SimpleNamespace(id="project-new", workdir_path="projects/new")

    class FakeAgentRunRepository:
        def __init__(self, _db):
            pass

        async def get_active_run_by_thread_for_user(self, **_kwargs):
            return None

    class FakeAgentRunRequestRepository:
        def __init__(self, _db):
            pass

        async def list_queued(self, **_kwargs):
            return []

    class FakeSubagentThreadRepository:
        def __init__(self, _db):
            pass

        async def get_by_child_conversation_for_user(self, _conversation_id, _uid):
            return SimpleNamespace(id=100, parent_conversation_id=10)

        async def get_by_parent_conversation_for_user(self, _conversation_id, _uid):
            return None

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(svc, "AgentRunRepository", FakeAgentRunRepository)
    monkeypatch.setattr(svc, "AgentRunRequestRepository", FakeAgentRunRequestRepository)
    monkeypatch.setattr(svc, "SubagentThreadRepository", FakeSubagentThreadRepository)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-child",
            project_id="project-new",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 409
    assert conversation.project_id == "project-old"


async def test_update_thread_view_rejects_unavailable_target_project(monkeypatch):
    conversation = SimpleNamespace(
        thread_id="thread-target",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return None

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-target",
            project_id="project-other-user",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 404
    assert conversation.project_id == "project-old"


async def test_update_thread_view_rejects_missing_target_workdir(monkeypatch):
    conversation = SimpleNamespace(
        thread_id="thread-workdir",
        uid="user-1",
        status="active",
        project_id="project-old",
        agent_id="main",
    )

    class FakeConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_thread_id(self, _thread_id):
            return conversation

    class FakeProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, _project_id, _uid):
            return SimpleNamespace(id="project-new", workdir_path="projects/missing")

    monkeypatch.setattr(svc, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", FakeProjectRepository)

    def fail_open_existing(*_args):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(svc.Workdir, "open_existing", fail_open_existing)

    with pytest.raises(svc.HTTPException) as exc_info:
        await svc.update_thread_view(
            thread_id="thread-workdir",
            project_id="project-new",
            db=object(),
            current_uid="user-1",
        )

    assert exc_info.value.status_code == 409
    assert conversation.project_id == "project-old"


async def test_explicit_project_creation_locks_project_until_commit(monkeypatch):
    project = SimpleNamespace(
        id="project-1",
        uid="user-1",
        status="active",
        selection_status="selectable",
        directory_mode="linked",
        workdir_path="clients/acme",
    )
    conversation = SimpleNamespace(
        id=1,
        thread_id="thread-1",
        project_id="project-1",
        uid="user-1",
    )
    lock_calls = []

    class _Db:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(uid="user-1"))

        async def commit(self):
            return None

    class _AgentRepository:
        def __init__(self, _db):
            pass

        async def get_visible_by_slug(self, **_kwargs):
            return SimpleNamespace(slug="main", backend_id="ChatbotAgent")

    class _ProjectRepository:
        def __init__(self, _db):
            pass

        async def lock_active_selectable_for_user(self, project_id, uid):
            lock_calls.append((project_id, uid, True))
            return project

    class _ConversationRepository:
        def __init__(self, _db):
            pass

        async def add_conversation(self, **_kwargs):
            return conversation

    async def serialize_thread(*_args, **_kwargs):
        return {"id": "thread-1"}

    monkeypatch.setattr(svc, "AgentRepository", _AgentRepository)
    monkeypatch.setattr(svc, "ProjectRepository", _ProjectRepository)
    monkeypatch.setattr(svc, "ConversationRepository", _ConversationRepository)
    monkeypatch.setattr(svc.Workdir, "open_existing", lambda *_args: None)
    monkeypatch.setattr(svc, "_serialize_thread", serialize_thread)

    result = await svc.create_thread_view(
        agent_slug="main",
        request_id=None,
        title="title",
        metadata={},
        project_id="project-1",
        db=_Db(),
        current_uid="user-1",
    )

    assert result == {"id": "thread-1"}
    assert lock_calls == [("project-1", "user-1", True)]


async def test_create_thread_replay_restores_managed_workdir(monkeypatch):
    project = SimpleNamespace(
        id="project-1",
        uid="user-1",
        status="active",
        selection_status="implicit",
        directory_mode="managed",
        workdir_path="projects/11111111-1111-4111-8111-111111111111",
    )
    conversation = SimpleNamespace(
        id=1,
        thread_id="thread-1",
        uid="user-1",
        agent_id="main",
        title="title",
        status="active",
        is_pinned=False,
        project_id=project.id,
        created_at=SimpleNamespace(isoformat=lambda: "created"),
        updated_at=SimpleNamespace(isoformat=lambda: "updated"),
        extra_metadata={},
    )

    class _Db:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(uid="user-1"))

    class _AgentRepository:
        def __init__(self, _db):
            pass

        async def get_visible_by_slug(self, **_kwargs):
            return SimpleNamespace(slug="main", backend_id="ChatbotAgent")

    class _ConversationRepository:
        def __init__(self, _db):
            pass

        async def get_conversation_by_creation_request_id(self, _uid, _request_id):
            return conversation

    class _ProjectRepository:
        def __init__(self, _db):
            pass

        async def get_for_user(self, _project_id, _uid):
            return project

    restored = []

    async def ensure_available(**kwargs):
        restored.append(kwargs["conversation"].thread_id)
        return project.workdir_path

    async def serialize_thread(_conversation, **_kwargs):
        return {"id": _conversation.thread_id}

    monkeypatch.setattr(svc, "AgentRepository", _AgentRepository)
    monkeypatch.setattr(svc, "ConversationRepository", _ConversationRepository)
    monkeypatch.setattr(svc, "ProjectRepository", _ProjectRepository)
    monkeypatch.setattr(svc, "ensure_conversation_workdir_available", ensure_available)
    monkeypatch.setattr(svc, "_serialize_thread", serialize_thread)

    result = await svc.create_thread_view(
        agent_slug="main",
        request_id="request-1",
        title="title",
        metadata={},
        project_id=None,
        db=_Db(),
        current_uid="user-1",
    )

    assert result == {"id": "thread-1"}
    assert restored == ["thread-1"]


async def test_marker_thread_with_terminal_run_shows_ready_then_done(session):
    await _seed_conversation(session, thread_id="thread-marker", last_viewed_run_id=UNVIEWED_RUN_MARKER)
    await _seed_run(session, thread_id="thread-marker", run_id="run-marker", status="completed")
    await session.commit()

    before = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    assert next(item for item in before if item["id"] == "thread-marker")["thread_status"] == "ready"

    await svc.mark_thread_viewed_view(db=session, thread_id="thread-marker", current_uid="user-1")
    after = await svc.list_threads_view(db=session, current_uid="user-1", agent_slug=None, limit=100)
    assert next(item for item in after if item["id"] == "thread-marker")["thread_status"] == "done"
