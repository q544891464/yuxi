"""在独立旧版本数据库中执行真实迁移器进程。"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, select, text

from yuxi.storage.postgres.models_business import Base, Department
from yuxi.storage.postgres.models_knowledge import Base as KnowledgeBase


def test_v9_to_v10_full_migrator_and_repeat(tmp_path):
    """v9 版本行和原记录经过完整迁移器升级，重复运行保留新文书数据。"""
    url = os.environ.get("TEST_NAV_DATABASE_URL", "")
    if not url:
        pytest.skip("需要独立 TEST_NAV_DATABASE_URL")
    assert "/nav_verify_" in url
    engine = create_engine(url.replace("postgresql+asyncpg", "postgresql+psycopg"))
    assert not inspect(engine).get_table_names(), "迁移测试必须独占空验证库"
    # 此变更只新增三张表；其余表组成已发布 v9 结构。
    old_tables = [t for t in Base.metadata.sorted_tables if not t.name.startswith("formal_document")]
    Base.metadata.create_all(engine, tables=old_tables)
    KnowledgeBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE yuxi_schema_migrations (domain VARCHAR(32) PRIMARY KEY, "
                "version INTEGER NOT NULL, applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(text("INSERT INTO yuxi_schema_migrations (domain,version) VALUES ('business',9),('knowledge',2)"))
        conn.execute(Department.__table__.insert().values(id=123, name="旧库保留部门"))
    environment = {**os.environ, "POSTGRES_URL": url}
    for key in [
        "YUXI_LEGACY_STORAGE_DIR",
        "YUXI_USER_DATA_DIR",
        "YUXI_SKILL_DATA_DIR",
        "YUXI_SKILL_PROJECTION_DIR",
        "YUXI_RUNTIME_DIR",
    ]:
        environment[key] = str(tmp_path / key.lower())
    try:
        for attempt in range(2):
            result = subprocess.run(
                [sys.executable, "-m", "yuxi.storage_migration"],
                env=environment,
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=90,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            with engine.connect() as conn:
                assert conn.scalar(text("SELECT version FROM yuxi_schema_migrations WHERE domain='business'")) == 10
                assert conn.scalar(select(Department.name).where(Department.id == 123)) == "旧库保留部门"
                assert {"formal_documents", "formal_document_files", "formal_document_events"} <= set(
                    inspect(conn).get_table_names()
                )
                if attempt:
                    assert (
                        conn.scalar(text("SELECT title FROM formal_documents WHERE id='migration-check'"))
                        == "升级后保留文书"
                    )
            if not attempt:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO formal_documents (id,title,case_number,creator_uid,status,step_index,revision,"
                            "workflow,readers,assignees,previous_assignees,created_at,updated_at) "
                            "VALUES ('migration-check','升级后保留文书','','fixture','draft',-1,0,"
                            "'{}','[]','[]','{}',NOW(),NOW())"
                        )
                    )
    finally:
        engine.dispose()
