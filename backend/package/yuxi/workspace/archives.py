"""ZIP 附件校验与受限解压，输出只写入当前 Workdir。"""

import stat
import struct
import tempfile
import uuid
import zipfile
import zlib
from contextlib import nullcontext
from pathlib import Path, PurePosixPath

MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_METADATA_BYTES = 8 * 1024 * 1024


def _check_zip_directory(source: str) -> None:
    """在 ZipFile 分配目录内存前，有界扫描真实条目，兼容单卷 ZIP64。"""
    with open(source, "rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
        index = tail.rfind(b"PK\x05\x06")
        if index < 0 or len(tail) - index < 22:
            raise ValueError("ZIP 无效：缺少结束记录")
        _, disk, directory_disk, disk_count, count, directory_size, directory_offset, comment = struct.unpack_from(
            "<4s4H2LH", tail, index
        )
        if index + 22 + comment != len(tail):
            raise ValueError("ZIP 无效：结束记录长度不一致")
        end = size - len(tail) + index
        if end >= 20:
            stream.seek(end - 20)
            locator = stream.read(20)
            if locator.startswith(b"PK\x06\x07"):
                _, locator_disk, zip64_offset, disks = struct.unpack("<4sLQL", locator)
                if locator_disk or disks != 1 or zip64_offset > end - 76:
                    raise ValueError("ZIP 无效：不支持分卷归档")
                stream.seek(zip64_offset)
                record = stream.read(56)
                if len(record) != 56 or not record.startswith(b"PK\x06\x06"):
                    raise ValueError("ZIP 无效：ZIP64 结束记录损坏")
                _, length, _, _, disk, directory_disk, disk_count, count, directory_size, directory_offset = (
                    struct.unpack("<4sQ2H2L4Q", record)
                )
                if length < 44 or zip64_offset + 12 + length != end - 20:
                    raise ValueError("ZIP 无效：ZIP64 结束记录长度错误")
                end = zip64_offset
        if disk or directory_disk or disk_count != count:
            raise ValueError("ZIP 无效：不支持分卷归档")
        if count > MAX_ZIP_ENTRIES:
            raise ValueError("ZIP 最多包含 1,000 个条目（含目录）")
        if directory_size > MAX_ZIP_METADATA_BYTES:
            raise ValueError("ZIP 目录元数据不能超过 8 MB")
        start = end - directory_size
        if start < 0 or directory_offset > start:
            raise ValueError("ZIP 无效：目录范围错误")
        actual_count = 0
        position = start
        while position < end:
            stream.seek(position)
            header = stream.read(46)
            if len(header) != 46 or not header.startswith(b"PK\x01\x02"):
                raise ValueError("ZIP 无效：目录条目损坏")
            actual_count += 1
            if actual_count > MAX_ZIP_ENTRIES:
                raise ValueError("ZIP 最多包含 1,000 个条目（含目录）")
            position += 46 + sum(struct.unpack_from("<3H", header, 28))
            if position > end:
                raise ValueError("ZIP 无效：目录条目长度错误")
        if actual_count != count:
            raise ValueError("ZIP 无效：目录条目数不一致")


def unpack_zip(source: str, output: str | None = None) -> dict:
    """校验全部条目与实际解压量，可选写入新建的本地临时目录。"""
    if Path(source).stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP 不能超过 200 MB")
    _check_zip_directory(source)
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError("ZIP 最多包含 1,000 个条目（含目录）")
            names = set()
            declared_size = 0
            for entry in entries:
                name = entry.orig_filename
                parts = name.rstrip("/").split("/")
                mode = entry.external_attr >> 16
                if (
                    not name
                    or name.startswith("/")
                    or "\\" in name
                    or ":" in name
                    or "\x00" in name
                    or any(part in {"", ".", ".."} for part in parts)
                    or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or entry.flag_bits & 1
                ):
                    raise ValueError("ZIP 包含不安全路径、链接、特殊文件或加密条目")
                normalized = "/".join(parts)
                if normalized in names:
                    raise ValueError("ZIP 包含重复路径")
                names.add(normalized)
                declared_size += entry.file_size
                if declared_size > MAX_EXPANDED_BYTES:
                    raise ValueError("ZIP 解压后总量不能超过 1 GB")
            total = 0
            files = 0
            for entry in entries:
                if entry.is_dir():
                    continue
                files += 1
                target = None
                if output is not None:
                    target = Path(output).joinpath(*PurePosixPath(entry.filename).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as stream:
                    with nullcontext() if target is None else target.open("xb") as destination:
                        while chunk := stream.read(1024 * 1024):
                            total += len(chunk)
                            if total > MAX_EXPANDED_BYTES:
                                raise ValueError("ZIP 解压后总量不能超过 1 GB")
                            if target is not None:
                                destination.write(chunk)
            return {"file_count": files, "expanded_bytes": total}
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError) as exc:
        raise ValueError(f"ZIP 无效或无法解压: {exc}") from exc


def extract_workdir_zip(workdir, source_scope: str) -> dict:
    """经 no-follow 文件边界读取 ZIP，成功校验后发布到独立项目目录。"""
    if PurePosixPath(source_scope).suffix.lower() != ".zip":
        raise ValueError("仅支持 ZIP 压缩包")
    with tempfile.TemporaryDirectory(prefix="yuxi-zip-") as temporary:
        source = str(Path(temporary) / "source.zip")
        Path(source).touch()
        workdir.copy_file_to_path(source_scope, source, MAX_ZIP_BYTES)
        unpacked = Path(temporary) / "unpacked"
        unpacked.mkdir()
        summary = unpack_zip(source, str(unpacked))
        directory = "extracted-" + uuid.uuid4().hex
        target_scope = "/" + directory
        workdir.create_directory("/", directory)
        try:
            for item in unpacked.rglob("*"):
                if item.is_file():
                    workdir.copy_file_from_path(
                        target_scope + "/" + item.relative_to(unpacked).as_posix(), str(item), overwrite=False
                    )
        except Exception:
            workdir.delete(target_scope)
            raise
        return {**summary, "directory": target_scope}
