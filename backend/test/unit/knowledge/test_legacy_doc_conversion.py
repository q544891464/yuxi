"""验证旧版 Word 转换的进程边界与产物校验。"""

import io
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from yuxi.utils import filepreview


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["timeout", "exit", "missing", "invalid", "not_word", "process_missing", "permission"]
)
async def test_doc_conversion_rejects_failed_or_invalid_output(monkeypatch, failure):
    """转换失败不伪装为成功，临时文件在所有失败路径清理。"""
    paths = []
    monkeypatch.setattr(filepreview, "_office_converter_executable", lambda: "soffice")

    def convert(command, **kwargs):
        """构造明确的转换器失败，不借助模型判断。"""
        directory = Path(command[command.index("--outdir") + 1])
        paths.append(directory)
        assert command[-1] == str(directory / "source.doc")
        assert kwargs["timeout"] > 0
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "process_missing":
            raise FileNotFoundError("soffice")
        if failure == "permission":
            raise PermissionError("process denied")
        if failure == "invalid":
            (directory / "source.docx").write_bytes(b"not a Word document")
        if failure == "not_word":
            with zipfile.ZipFile(directory / "source.docx", "w") as archive:
                archive.writestr("unrelated.txt", "not Word")
        return SimpleNamespace(returncode=1 if failure == "exit" else 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(filepreview.subprocess, "run", convert)
    with pytest.raises(filepreview.OfficePreviewConversionError):
        await filepreview.convert_doc_to_docx("案件.DOC", b"source")
    assert paths and all(not p.exists() for p in paths)


@pytest.mark.asyncio
async def test_doc_conversion_validates_word_content_and_preserves_pdf_preview(monkeypatch):
    """新 DOCX 用途和既有 PDF 预览均保留各自产物类型。"""
    stream = io.BytesIO()
    document = Document()
    document.add_paragraph("合成测试正文")
    document.save(stream)
    word = stream.getvalue()
    profiles = []
    monkeypatch.setattr(filepreview, "_office_converter_executable", lambda: "soffice")

    def convert(command, **kwargs):
        """按请求格式写入对应的可验证输出。"""
        profiles.append(next(x for x in command if x.startswith("-env:UserInstallation=")))
        directory = Path(command[command.index("--outdir") + 1])
        target = command[command.index("--convert-to") + 1]
        if target == "pdf":
            (directory / "source.pdf").write_bytes(b"%PDF-1.4\npreview")
        else:
            assert target == "docx:Office Open XML Text"
            (directory / "source.docx").write_bytes(word)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(filepreview.subprocess, "run", convert)
    assert await filepreview.convert_doc_to_docx("report.doc", b"source") == word
    assert await filepreview.convert_office_to_pdf("report.docx", word) == b"%PDF-1.4\npreview"
    assert profiles[0] != profiles[1]


@pytest.mark.asyncio
async def test_doc_converter_rejects_unrelated_format_before_process(monkeypatch):
    """专用 DOC 转换入口不扩大成任意文件转换器。"""
    monkeypatch.setattr(filepreview, "_office_converter_executable", lambda: pytest.fail("不应启动转换器"))
    with pytest.raises(filepreview.OfficePreviewConversionError, match="不支持"):
        await filepreview.convert_doc_to_docx("image.png", b"source")


@pytest.mark.asyncio
async def test_doc_conversion_wraps_temporary_file_errors(monkeypatch):
    """临时目录无法写入时仍返回统一转换异常。"""
    monkeypatch.setattr(filepreview, "_office_converter_executable", lambda: "soffice")

    def deny_write(*args, **kwargs):
        """模拟临时目录的权限失败。"""
        raise PermissionError("write denied")

    monkeypatch.setattr(Path, "write_bytes", deny_write)
    with pytest.raises(filepreview.OfficePreviewConversionError, match="临时文件"):
        await filepreview.convert_doc_to_docx("report.doc", b"source")
