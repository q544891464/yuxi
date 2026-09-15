"""ZIP 附件的独立边界与解压输出验证。"""

import stat
import struct
import zipfile
from types import SimpleNamespace

import pytest

from yuxi.workspace import archives
from yuxi.workspace import filesystem as filesystem_module
from yuxi.workspace.workdir import Workdir


def make_zip(path, entries):
    """按输入条目构造真实 ZIP。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in entries:
            bundle.writestr(name, data)
    return str(path)


def test_zip_extract_preserves_content(tmp_path):
    source = make_zip(tmp_path / "case.zip", [("材料/报告.txt", "报告正文"), ("a.txt", "abc")])
    output = tmp_path / "out"
    output.mkdir()
    summary = archives.unpack_zip(source, str(output))
    assert (output / "材料/报告.txt").read_text() == "报告正文"
    assert summary == {"file_count": 2, "expanded_bytes": len("报告正文".encode()) + 3}


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/bad", "a\\b", "a/../b", "a//b"])
def test_zip_rejects_unsafe_paths_before_output(tmp_path, name):
    source = make_zip(tmp_path / "case.zip", [("valid.txt", "safe"), (name, "bad")])
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError, match="不安全路径"):
        archives.unpack_zip(source, str(output))
    assert list(output.iterdir()) == []


def test_zip_rejects_symlink(tmp_path):
    entry = zipfile.ZipInfo("link")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    source = make_zip(tmp_path / "case.zip", [(entry, "/outside")])
    with pytest.raises(ValueError, match="链接"):
        archives.unpack_zip(source)


def test_zip_entry_count_boundary(tmp_path):
    source = make_zip(tmp_path / "case.zip", [(str(i), "") for i in range(1000)])
    assert archives.unpack_zip(source)["file_count"] == 1000
    with zipfile.ZipFile(source, "a") as bundle:
        bundle.writestr("extra", "")
    with pytest.raises(ValueError, match="1,000"):
        archives.unpack_zip(source)


def test_zip_forged_entry_count_rejected_before_zipfile_allocates(tmp_path, monkeypatch):
    source = make_zip(tmp_path / "case.zip", [(str(i), "") for i in range(1001)])
    path = tmp_path / "case.zip"
    data = bytearray(path.read_bytes())
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<2H", data, end + 8, 0, 0)
    path.write_bytes(data)

    def forbidden(*args, **kwargs):
        """超过条目限制前不得构造 ZipInfo 列表。"""
        raise AssertionError("ZipFile allocated before entry check")

    monkeypatch.setattr(archives.zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="1,000"):
        archives.unpack_zip(source)


def test_zip_metadata_budget_rejected_before_zipfile_allocates(tmp_path, monkeypatch):
    source = make_zip(tmp_path / "case.zip", [("a", "")])
    path = tmp_path / "case.zip"
    data = bytearray(path.read_bytes())
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<L", data, end + 12, 8 * 1024**2 + 1)
    path.write_bytes(data)

    def forbidden(*args, **kwargs):
        """拒绝在元数据限额校验之前加载目录。"""
        raise AssertionError("ZipFile allocated before metadata check")

    monkeypatch.setattr(archives.zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="8 MB"):
        archives.unpack_zip(source)


def test_zip64_single_volume_supported(tmp_path):
    source = make_zip(tmp_path / "case.zip", [("a", "content")])
    path = tmp_path / "case.zip"
    data = path.read_bytes()
    end = data.rfind(b"PK\x05\x06")
    _, _, _, _, count, size, offset, _ = struct.unpack("<4s4H2LH", data[end:])
    record = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45, 0, 0, count, count, size, offset)
    locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, end, 1)
    ending = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 65535, 65535, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    path.write_bytes(data[:end] + record + locator + ending)
    assert archives.unpack_zip(source)["file_count"] == 1


def test_zip_expansion_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(archives, "MAX_EXPANDED_BYTES", 32)
    source = make_zip(tmp_path / "case.zip", [("a", "x" * 32)])
    assert archives.unpack_zip(source)["expanded_bytes"] == 32
    source = make_zip(tmp_path / "large.zip", [("a", "x" * 33)])
    with pytest.raises(ValueError, match="1 GB"):
        archives.unpack_zip(source)


def test_zip_rejects_nonzip(tmp_path):
    source = tmp_path / "fake.zip"
    source.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="ZIP 无效"):
        archives.unpack_zip(str(source))


def test_zip_rejects_duplicate_paths(tmp_path):
    with pytest.warns(UserWarning, match="Duplicate"):
        source = make_zip(tmp_path / "case.zip", [("same", "a"), ("same", "b")])
    with pytest.raises(ValueError, match="重复"):
        archives.unpack_zip(source)


def test_zip_rejects_encrypted_entry(tmp_path):
    source = make_zip(tmp_path / "case.zip", [("a", "content")])
    path = tmp_path / "case.zip"
    data = bytearray(path.read_bytes())
    offset = data.index(b"PK\x01\x02")
    struct.pack_into("<H", data, offset + 8, 1)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="加密"):
        archives.unpack_zip(source)


@pytest.mark.asyncio
async def test_zip_tool_available_without_agent_configuration():
    from yuxi.agents.toolkits.service import resolve_configured_runtime_tools

    tools = await resolve_configured_runtime_tools(SimpleNamespace(tools=[], mcps=[]))
    assert sum(tool.name == "extract_zip" for tool in tools) == 1


def test_zip_compressed_size_boundary(tmp_path, monkeypatch):
    source = make_zip(tmp_path / "case.zip", [("a", "abc")])
    size = (tmp_path / "case.zip").stat().st_size
    monkeypatch.setattr(archives, "MAX_ZIP_BYTES", size)
    assert archives.unpack_zip(source)["file_count"] == 1
    monkeypatch.setattr(archives, "MAX_ZIP_BYTES", size - 1)
    with pytest.raises(ValueError, match="200 MB"):
        archives.unpack_zip(source)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """创建真实隔离用户目录，使用实际 no-follow 文件实现。"""
    relative = "projects/11111111-1111-4111-8111-111111111111"
    root = tmp_path / "user-1"
    (root / relative).mkdir(parents=True)
    monkeypatch.setattr(filesystem_module, "user_workspace_dir", lambda uid: tmp_path / uid)
    return Workdir.open_existing("user-1", relative)


def test_workdir_extract_and_rollback(tmp_path, workdir, monkeypatch):
    source = make_zip(tmp_path / "source.zip", [("sub/report.txt", "case"), ("b.txt", "second")])
    workdir.copy_file_from_path("/case.zip", source)
    result = archives.extract_workdir_zip(workdir, "/case.zip")
    assert workdir.read_file(result["directory"] + "/sub/report.txt", 100) == b"case"
    before = workdir.list_directory("/")
    original = Workdir.copy_file_from_path

    def fail_second(self, path, source_path, **kwargs):
        """模拟部分文件写入后的磁盘错误。"""
        if path.endswith("/report.txt"):
            raise OSError("disk full")
        return original(self, path, source_path, **kwargs)

    monkeypatch.setattr(Workdir, "copy_file_from_path", fail_second)
    with pytest.raises(OSError):
        archives.extract_workdir_zip(workdir, "/case.zip")
    assert workdir.list_directory("/") == before


@pytest.mark.asyncio
async def test_agent_zip_tool_uses_current_workdir(tmp_path, workdir):
    from yuxi.agents.toolkits.buildin.tools import extract_zip

    source = make_zip(tmp_path / "source.zip", [("report.txt", "case")])
    workdir.copy_file_from_path("/case.zip", source)
    root = "/home/gem/user-data/" + workdir.relative_path
    runtime = SimpleNamespace(
        config={
            "configurable": {
                "thread_id": "thread-1",
                "uid": "user-1",
                "workdir_relative_path": workdir.relative_path,
            }
        }
    )
    result = await extract_zip.coroutine(file_path=root + "/case.zip", runtime=runtime)
    assert result["file_count"] == 1
    assert result["directory"].startswith(root + "/extracted-")
    rejected = await extract_zip.coroutine(file_path="/home/gem/user-data/another/case.zip", runtime=runtime)
    assert rejected["status"] == "error"


def test_zip_source_symlink_cannot_escape(tmp_path, workdir):
    outside = tmp_path / "outside.zip"
    make_zip(outside, [("report.txt", "outside")])
    root = tmp_path / "user-1" / workdir.relative_path
    (root / "link.zip").symlink_to(outside)
    with pytest.raises((ValueError, PermissionError, OSError)):
        archives.extract_workdir_zip(workdir, "/link.zip")
