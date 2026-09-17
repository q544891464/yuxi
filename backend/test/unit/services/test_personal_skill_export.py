"""个人技能导出的文件内容、隔离与清理契约。"""

import os
import errno
import zipfile
from pathlib import Path

import pytest

from yuxi.agents.skills import service as svc


@pytest.fixture
def personal_root(tmp_path, monkeypatch):
    """使用真实临时文件，隔离用户目录与导出目录。"""
    monkeypatch.setattr(svc, "get_personal_skills_root_dir", lambda uid: tmp_path / uid)
    exports = tmp_path / "exports"
    exports.mkdir()
    monkeypatch.setattr(svc.tempfile, "tempdir", str(exports))
    root = tmp_path / "alice" / "demo"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_bytes(b"# personal skill\n")
    return root


@pytest.mark.asyncio
async def test_export_preserves_tree_bytes_and_executable_mode(personal_root):
    """导出内容可直接解包，包含二进制、空目录与可执行脚本。"""
    (personal_root / "empty").mkdir()
    (personal_root / "scripts").mkdir()
    script = personal_root / "scripts" / "run.sh"
    script.write_bytes(b"#!/bin/sh\necho ok\n")
    script.chmod(0o755)
    (personal_root / "资源.bin").write_bytes(bytes(range(256)))
    path, name = await svc.export_personal_skill_zip("alice", "demo")
    try:
        assert name == "demo.zip"
        with zipfile.ZipFile(path) as archive:
            assert set(archive.namelist()) == {
                "demo/SKILL.md",
                "demo/empty/",
                "demo/scripts/",
                "demo/scripts/run.sh",
                "demo/资源.bin",
            }
            assert archive.read("demo/SKILL.md") == b"# personal skill\n"
            assert archive.read("demo/资源.bin") == bytes(range(256))
            assert archive.read("demo/scripts/run.sh") == script.read_bytes()
            assert (archive.getinfo("demo/scripts/run.sh").external_attr >> 16) & 0o777 == 0o755
    finally:
        Path(path).unlink()


@pytest.mark.asyncio
async def test_install_personal_skill_replaces_existing_directory_atomically(personal_root, tmp_path, monkeypatch):
    """同名个人 Skill 更新后只保留新目录，失败前的旧目录仍可恢复。"""
    monkeypatch.setattr(svc, "_personal_skills_root", lambda uid: personal_root.parent)
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: updated\n---\n# Updated\n")
    old = personal_root / "legacy.txt"
    old.write_text("old")
    updated = await svc.install_personal_skill_dir("alice", source, expected_slug="demo", replace_existing=True)
    assert updated.slug == "demo"
    assert (personal_root / "SKILL.md").read_text().endswith("# Updated\n")
    assert not old.exists()


@pytest.mark.asyncio
async def test_install_personal_skill_restores_old_directory_when_publish_fails(personal_root, tmp_path, monkeypatch):
    """发布暂存目录失败时，旧个人 Skill 必须恢复。"""
    monkeypatch.setattr(svc, "_personal_skills_root", lambda uid: personal_root.parent)
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: updated\n---\n# Updated\n")

    original_rename = Path.rename

    def fail_publish(path, target):
        if path.name.startswith(".install.tmp-"):
            raise OSError("publish failed")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_publish)
    with pytest.raises(OSError, match="publish failed"):
        await svc.install_personal_skill_dir("alice", source, expected_slug="demo", replace_existing=True)
    assert (personal_root / "SKILL.md").read_bytes() == b"# personal skill\n"


def test_personal_update_probe_rejects_symlinked_workspace_component(tmp_path, monkeypatch):
    """预览检查遇到工作区符号链接时必须 fail-closed。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    (outside / "demo").mkdir()
    monkeypatch.setattr(svc, "get_personal_skills_root_dir", lambda uid: linked)
    assert svc._personal_skill_exists_for_update("alice", "demo") is False


def test_recover_pending_personal_install_restores_backup(tmp_path):
    """进程中断后再次访问个人 Skill 时恢复旧目录并清理暂存目录。"""
    root = tmp_path / "skills"
    root.mkdir()
    backup = root / ".install.backup-test"
    backup.mkdir()
    (backup / "SKILL.md").write_text("old")
    temp = root / ".install.tmp-test"
    temp.mkdir()
    (root / ".install.pending.json").write_text(
        '{"slug":"demo","backup":".install.backup-test","temp":".install.tmp-test"}'
    )
    svc._recover_pending_personal_install(root)
    assert (root / "demo" / "SKILL.md").read_text() == "old"
    assert not backup.exists()
    assert not temp.exists()
    assert not (root / ".install.pending.json").exists()


@pytest.mark.asyncio
async def test_export_does_not_fallback_to_another_user(personal_root):
    """同名技能不存在时，不能从其他用户目录返回内容。"""
    with pytest.raises(ValueError, match="不存在"):
        await svc.export_personal_skill_zip("bob", "demo")
    bob = personal_root.parents[1] / "bob" / "demo"
    bob.mkdir(parents=True)
    (bob / "SKILL.md").write_bytes(b"bob")
    path, _ = await svc.export_personal_skill_zip("bob", "demo")
    try:
        with zipfile.ZipFile(path) as archive:
            assert archive.read("demo/SKILL.md") == b"bob"
    finally:
        Path(path).unlink()


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", ["../alice/demo", "demo/../../alice", "demo\\file", ""])
async def test_export_rejects_invalid_slug(personal_root, slug):
    """路径输入不能突破个人技能根目录。"""
    with pytest.raises(ValueError, match="slug"):
        await svc.export_personal_skill_zip("alice", slug)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["file-link", "dir-link", "root-link", "fifo", "missing-manifest", "manifest-link"])
async def test_export_refuses_unsafe_entries_and_removes_partial_zip(personal_root, kind):
    """不读取链接目标或特殊文件，任何失败都不能遗留半成品归档。"""
    outside = personal_root.parents[1] / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("secret")
    if kind == "file-link":
        (personal_root / "secret").symlink_to(outside / "SKILL.md")
    elif kind == "dir-link":
        (personal_root / "secret").symlink_to(outside, target_is_directory=True)
    elif kind == "root-link":
        (personal_root / "SKILL.md").unlink()
        personal_root.rmdir()
        personal_root.symlink_to(outside, target_is_directory=True)
    elif kind == "fifo":
        os.mkfifo(personal_root / "pipe")
    else:
        (personal_root / "SKILL.md").unlink()
        if kind == "manifest-link":
            (personal_root / "SKILL.md").symlink_to(outside / "SKILL.md")
    with pytest.raises(ValueError):
        await svc.export_personal_skill_zip("alice", "demo")
    assert list((personal_root.parents[1] / "exports").iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["create", "write"])
async def test_export_preserves_server_io_error_and_cleans_partial_archive(personal_root, monkeypatch, stage):
    """临时磁盘故障保留服务器异常类别，并清理已生成的归档。"""

    def disk_full(*args, **kwargs):
        """模拟真实 I/O 边界的磁盘空间不足。"""
        raise OSError(errno.ENOSPC, "No space left on device")

    if stage == "create":
        monkeypatch.setattr(svc.tempfile, "mkstemp", disk_full)
    else:
        monkeypatch.setattr(svc.zipfile.ZipFile, "open", disk_full)
    with pytest.raises(OSError) as error:
        await svc.export_personal_skill_zip("alice", "demo")
    assert error.value.errno == errno.ENOSPC
    assert list((personal_root.parents[1] / "exports").iterdir()) == []
