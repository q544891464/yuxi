"""通过真实 Git 导出验证跨平台 shell 换行。"""

import io
from pathlib import Path
import subprocess
import tarfile

import pytest


@pytest.mark.parametrize("autocrlf,with_attributes", [("true", True), ("false", True), ("true", False)])
def test_shell_archive_preserves_lf(tmp_path: Path, autocrlf: str, with_attributes: bool):
    """无属性的负向对照必须恢复 Windows 导出 CRLF 的缺陷。"""
    source = b"#!/bin/sh\nprintf 'ready\\n'\n"
    (tmp_path / "init.sh").write_bytes(source)
    if with_attributes:
        attributes = Path(__file__).resolve().parents[4] / ".gitattributes"
        (tmp_path / ".gitattributes").write_bytes(attributes.read_bytes())

    def git(*args):
        """仅在临时仓库执行 Git，不依赖调用者身份配置。"""
        return subprocess.check_output(
            [
                "git",
                "-c",
                f"core.autocrlf={autocrlf}",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=tmp_path,
            stderr=subprocess.PIPE,
        )

    git("init")
    git("add", ".")
    git("-c", "commit.gpgsign=false", "commit", "-m", "fixture")
    with tarfile.open(fileobj=io.BytesIO(git("archive", "HEAD"))) as archive:
        exported = archive.extractfile("init.sh").read()
    expected = source if with_attributes else source.replace(b"\n", b"\r\n")
    assert exported == expected
