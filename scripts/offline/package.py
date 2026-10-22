#!/usr/bin/env python3
"""从生产 Compose 和已验证的 ARM64 镜像生成离线部署包。"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import re
import tarfile
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SERVICE_TYPE = {
    "api": "api",
    "worker": "api",
    "storage-migrator": "api",
    "sandbox-runtime-image": "sandbox",
    "sandbox-provisioner": "provisioner",
    "web": "web",
    "graph": "neo4j",
    "etcd": "etcd",
    "minio": "minio",
    "milvus": "milvus",
    "postgres": "postgres",
    "redis": "redis",
}
EXPECTED_TYPES = {"api", "web", "provisioner", "sandbox", "minio", "postgres", "redis", "neo4j", "etcd", "milvus"}
REQUIRED_COMPONENTS = ("compose.yaml", "install.py", "verify.py", "sandbox-smoke.py", "ocr-smoke.py", "sandbox.env", "README.md")
REVISION_IMAGE_TYPES = {"api", "web", "provisioner", "sandbox"}
REMOVED_SERVICES = {"mineru-api", "paddlex"}
SOURCE_PATHS = (
    ".dockerignore", "docker-compose.prod.yml", "backend/pyproject.toml", "backend/.python-version", "backend/uv.lock",
    "backend/package", "backend/server", "web", "docker",
)


def fail(message: str) -> "NoReturn":
    """以可读诊断结束打包。"""
    raise SystemExit(message)


def digest(path: Path) -> str:
    """计算文件 SHA256。"""
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def docker_json(*args: str) -> dict[str, Any]:
    """运行 Docker 并读取一条 JSON 结果。"""
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)[0]


def resolve_source_revision(explicit: str | None) -> str:
    """解析 Git 版本并拒绝与打包镜像输入相关的未提交改动。"""
    if explicit is not None and not re.fullmatch(r"[0-9a-f]{40}", explicit):
        fail("source revision 必须是完整的 40 位小写 Git SHA")
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        if explicit is None:
            fail("非 Git 源码包必须通过 --source-revision 显式指定镜像源码版本")
        return explicit
    if explicit is not None and explicit != head:
        fail(f"--source-revision 与当前 Git HEAD 不一致：{explicit} != {head}")
    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS],
        check=True, capture_output=True, text=True,
    ).stdout
    if status.strip():
        fail("镜像源码输入存在未提交改动；请先提交后再打包")
    return head


def validate_image_revision(image_type: str, info: dict[str, Any], source_revision: str) -> None:
    """要求应用镜像的 OCI revision 标签匹配源码提交。"""
    if image_type not in REVISION_IMAGE_TYPES:
        return
    labels = (info.get("Config") or {}).get("Labels") or {}
    if not isinstance(labels, dict) or labels.get("org.opencontainers.image.revision") != source_revision:
        fail(f"{image_type} 镜像必须带有匹配的 org.opencontainers.image.revision 标签")


def archive_config_digest(archive_path: Path, reference: str) -> str:
    """读取镜像归档的单个 config blob 并返回其 SHA256 身份。"""
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            manifest_member = archive.getmember("manifest.json")
            if not manifest_member.isfile():
                fail("镜像归档 manifest.json 必须是普通文件")
            manifest_file = archive.extractfile(manifest_member)
            if manifest_file is None:
                fail("镜像归档缺少可读 manifest.json")
            entries = json.loads(manifest_file.read())
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                fail("镜像归档 manifest.json 格式无效")
            matches = [entry for entry in entries if reference in (entry.get("RepoTags") or [])]
            if not matches and len(entries) == 1 and not entries[0].get("RepoTags"):
                matches = entries
            if len(matches) != 1:
                fail(f"镜像归档必须包含且只包含目标引用：{reference}")
            config_path = matches[0].get("Config")
            relative_config = PurePosixPath(config_path) if isinstance(config_path, str) else None
            if relative_config is None or not config_path or relative_config.is_absolute() or ".." in relative_config.parts:
                fail("镜像归档 Config 路径无效")
            config_member = archive.getmember(config_path)
            if not config_member.isfile():
                fail("镜像归档 Config 必须是普通文件")
            config_file = archive.extractfile(config_member)
            if config_file is None:
                fail("镜像归档缺少可读 Config 文件")
            return "sha256:" + hashlib.sha256(config_file.read()).hexdigest()
    except (OSError, tarfile.TarError, KeyError, ValueError, TypeError) as exc:
        fail(f"无法读取镜像归档 config digest：{exc}")


def save_compressed_image(reference: str, destination: Path) -> None:
    """将 Docker image save 流直接压缩到归档文件。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(["docker", "image", "save", reference], stdout=subprocess.PIPE)
    try:
        assert process.stdout is not None
        with destination.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1) as zipped:
            shutil.copyfileobj(process.stdout, zipped, length=1024 * 1024)
        code = process.wait()
        if code:
            destination.unlink(missing_ok=True)
            fail(f"docker image save 失败：{reference} (exit={code})")
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        destination.unlink(missing_ok=True)
        raise


def rewrite_compose(source: dict[str, Any], image_map: dict[str, str]) -> dict[str, Any]:
    """移除构建和 GPU OCR，仅保留 Basic 运行拓扑。"""
    services = source.get("services")
    if not isinstance(services, dict):
        fail("生产 Compose 缺少 services")
    if not REMOVED_SERVICES <= set(services):
        fail("生产 Compose 的可选 OCR 服务名称与离线打包契约不符")
    if not set(SERVICE_TYPE) <= set(services):
        fail(f"生产 Compose 缺少离线 Basic 服务：{', '.join(sorted(set(SERVICE_TYPE) - set(services)))}")
    unknown = set(services) - set(SERVICE_TYPE) - REMOVED_SERVICES
    if unknown:
        fail(f"离线打包尚未声明这些 Compose 服务的镜像类型：{', '.join(sorted(unknown))}")
    if set(image_map) != set(SERVICE_TYPE):
        missing = sorted(set(SERVICE_TYPE) - set(image_map))
        extra = sorted(set(image_map) - set(SERVICE_TYPE))
        fail(f"image map 服务不匹配；缺少={missing}，多余={extra}")
    by_type: dict[str, str] = {}
    for service, image_type in SERVICE_TYPE.items():
        reference = image_map[service]
        if not isinstance(reference, str) or not reference or "${" in reference:
            fail(f"服务 {service} 必须使用固定镜像引用")
        previous = by_type.setdefault(image_type, reference)
        if previous != reference:
            fail(f"同一镜像类型引用不一致：{image_type}")

    result = dict(source)
    result_services = {name: dict(config) for name, config in services.items() if name not in REMOVED_SERVICES}
    for name, config in result_services.items():
        config.pop("build", None)
        config.pop("container_name", None)
        config.pop("profiles", None)
        config.pop("env_file", None)
        config["image"] = image_map[name]
        config["pull_policy"] = "never"
        if name in {"api", "worker", "storage-migrator"}:
            environment = config.setdefault("environment", {})
            if not isinstance(environment, dict):
                fail(f"服务 {name} 的 environment 必须是映射，无法注入 MinIO 凭据")
            environment["MINIO_ACCESS_KEY"] = "${MINIO_ACCESS_KEY:?Set MINIO_ACCESS_KEY in offline .env}"
            environment["MINIO_SECRET_KEY"] = "${MINIO_SECRET_KEY:?Set MINIO_SECRET_KEY in offline .env}"
        config.pop("ports", None)
        if name == "web":
            config["ports"] = ["${YUXI_WEB_PORT:-18080}:80"]
    result["services"] = result_services
    result["name"] = "smartstaff-offline"
    return result


def build_bundle(compose_path: Path, map_path: Path, output: Path, source_revision: str | None = None) -> None:
    """验证镜像并写入 Compose、归档和摘要清单。"""
    try:
        import yaml
    except ImportError:
        fail("打包机需要 PyYAML：python -m pip install pyyaml")
    if output.exists():
        fail(f"输出目录已存在，拒绝覆盖：{output}")
    try:
        source = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        image_map = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        fail(f"无法读取 Compose 或 image map：{exc}")
    if not isinstance(image_map, dict):
        fail("image map 必须是服务名到镜像引用的 JSON 对象")
    source_revision = resolve_source_revision(source_revision)
    frozen = rewrite_compose(source, image_map)

    output.mkdir(parents=True)
    try:
        images_dir = output / "images"
        manifest: list[dict[str, str]] = []
        seen_types: set[str] = set()
        for service, image_type in SERVICE_TYPE.items():
            if image_type in seen_types:
                continue
            seen_types.add(image_type)
            reference = image_map[service]
            info = docker_json("image", "inspect", reference)
            if info.get("Os") != "linux" or info.get("Architecture") != "arm64":
                fail(f"镜像必须是 linux/arm64：{reference} ({info.get('Os')}/{info.get('Architecture')})")
            validate_image_revision(image_type, info, source_revision)
            image_id = info.get("Id", "")
            if not image_id.startswith("sha256:") or len(image_id) != 71:
                fail(f"Docker 未返回完整 SHA256 image ID：{reference}")
            archive = f"images/{image_type}.tar.gz"
            archive_path = output / archive
            save_compressed_image(reference, archive_path)
            config_digest = archive_config_digest(archive_path, reference)
            manifest.append({
                "type": image_type,
                "reference": reference,
                "image_id": image_id,
                "config_digest": config_digest,
                "architecture": "arm64",
                "archive": archive,
                "sha256": digest(archive_path),
            })
        if seen_types != EXPECTED_TYPES:
            fail(f"离线镜像类型契约不完整：{sorted(seen_types)}")
        (output / "compose.yaml").write_text(yaml.safe_dump(frozen, sort_keys=False, allow_unicode=True), encoding="utf-8")
        for name in ("install.py", "verify.py", "README.md"):
            shutil.copy2(Path(__file__).with_name(name), output / name)
        for name in ("sandbox-smoke.py", "ocr-smoke.py"):
            shutil.copy2(ROOT / "docker" / "offline" / name, output / name)
        # Runtime configuration template intentionally contains no deployment credentials.
        (output / "sandbox.env").write_text("CHECK_YUXI_SANDBOX_ENV_EXISTS=True\n", encoding="utf-8")
        components = {name: digest(output / name) for name in REQUIRED_COMPONENTS}
        (output / "manifest.json").write_text(
            json.dumps({
                "schema_version": 1,
                "platform": "linux/arm64",
                "source_revision": source_revision,
                "components": components,
                "images": manifest,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise


def main() -> int:
    """解析打包参数并生成离线包。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, default=ROOT / "docker-compose.prod.yml")
    parser.add_argument("--image-map", type=Path, required=True, help="JSON：Compose 服务名映射到不可变 ARM64 镜像引用")
    parser.add_argument("--source-revision", help="非 Git 源码包必填；Git 工作区默认 HEAD，且相关构建输入必须干净")
    parser.add_argument("--output", type=Path, required=True, help="必须尚不存在的输出目录")
    args = parser.parse_args()
    build_bundle(args.compose.resolve(), args.image_map.resolve(), args.output.resolve(), args.source_revision)
    print(f"离线包已生成：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
