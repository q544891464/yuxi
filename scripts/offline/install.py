#!/usr/bin/env python3
"""在 ARM64 Docker 主机上无网络安装全新 Yuxi Basic。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, NoReturn


IMAGE_TYPES = {"api", "web", "provisioner", "sandbox", "minio", "postgres", "redis", "neo4j", "etcd", "milvus"}
REQUIRED_COMPONENTS = {"compose.yaml", "install.py", "verify.py", "sandbox-smoke.py", "ocr-smoke.py", "sandbox.env", "README.md"}
REVISION_IMAGE_TYPES = {"api", "web", "provisioner", "sandbox"}


class InstallError(RuntimeError):
    """表示离线安装前置条件或执行步骤失败。"""


def require(condition: bool, message: str) -> None:
    """前置条件不成立时停止安装。"""
    if not condition:
        raise InstallError(message)


def sha256_file(path: Path) -> str:
    """流式计算归档 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(bundle: Path, *, verify_archives: bool = True) -> tuple[dict[str, Any], list[tuple[dict[str, str], Path | None]]]:
    """验证清单结构、组件摘要及可选的镜像归档摘要。"""
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"无法读取 manifest.json：{exc}") from exc
    require(isinstance(manifest, dict), "离线包清单必须是 JSON 对象")
    require(manifest.get("schema_version") == 1, "不支持的离线包清单版本")
    require(manifest.get("platform") == "linux/arm64", "离线包平台必须为 linux/arm64")
    require(isinstance(manifest.get("source_revision"), str) and re.fullmatch(r"[0-9a-f]{40}", manifest["source_revision"]), "清单 source_revision 必须是完整 Git SHA")
    entries = manifest.get("images")
    require(isinstance(entries, list), "manifest images 必须是数组")
    require({item.get("type") for item in entries if isinstance(item, dict)} == IMAGE_TYPES, "清单必须恰好包含十种 Basic 镜像")
    require(len(entries) == len(IMAGE_TYPES), "清单存在重复镜像类型")
    verified: list[tuple[dict[str, str], Path | None]] = []
    refs: set[str] = set()
    image_ids: set[str] = set()
    config_digests: set[str] = set()
    for entry in entries:
        require(isinstance(entry, dict), "镜像条目格式错误")
        reference = entry.get("reference")
        image_id = entry.get("image_id")
        archive = entry.get("archive")
        checksum = entry.get("sha256")
        require(entry.get("architecture") == "arm64", f"{entry.get('type')} 镜像架构不是 arm64")
        require(isinstance(reference, str) and reference and "${" not in reference, "镜像引用必须固定")
        require(isinstance(image_id, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id), "镜像 ID 必须是完整 SHA256")
        config_digest = entry.get("config_digest")
        require(isinstance(config_digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", config_digest), "镜像 config digest 必须是完整 SHA256")
        require(isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum), "归档 SHA256 格式错误")
        archive_path = None
        require(isinstance(archive, str) and archive.startswith("images/") and ".." not in Path(archive).parts, "归档路径必须位于 images/ 下")
        archive_path = (bundle / archive).resolve()
        require(archive_path.is_relative_to(bundle.resolve()), "归档路径越出离线包目录")
        if verify_archives:
            require(archive_path.is_file(), f"缺少镜像归档：{archive}")
            require(sha256_file(archive_path) == checksum, f"镜像归档 SHA256 不匹配：{archive}")
        else:
            archive_path = None
        require(reference not in refs and image_id not in image_ids and config_digest not in config_digests, "镜像清单中的引用、image ID 和 config digest 必须唯一")
        refs.add(reference)
        image_ids.add(image_id)
        config_digests.add(config_digest)
        verified.append((entry, archive_path))
    components = manifest.get("components")
    require(isinstance(components, dict) and components, "清单缺少组件摘要")
    require(set(components) == REQUIRED_COMPONENTS, "清单必须恰好校验全部只读部署组件")
    for name, checksum in components.items():
        require(isinstance(name, str) and Path(name).name == name and name not in {"manifest.json", ".env"}, "组件路径必须是包根目录下的文件")
        require(isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum), "组件 SHA256 格式错误")
        component = bundle / name
        require(component.resolve().is_relative_to(bundle.resolve()), f"组件路径越出离线包目录：{name}")
        require(component.is_file() and sha256_file(component) == checksum, f"组件 SHA256 不匹配：{name}")
    return manifest, verified


def run(command: list[str], *, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """执行系统命令并把失败转成带命令的错误。"""
    result = subprocess.run(command, cwd=cwd, check=False, text=True, capture_output=capture)
    if result.returncode:
        detail = result.stderr.strip() if capture and result.stderr else ""
        raise InstallError(f"命令失败 (exit={result.returncode}): {' '.join(command)}{': ' + detail if detail else ''}")
    return result


def docker_inspect(reference: str) -> dict[str, Any]:
    """读取本机 Docker 镜像事实。"""
    result = run(["docker", "image", "inspect", reference], capture=True)
    try:
        return json.loads(result.stdout)[0]
    except (ValueError, IndexError) as exc:
        raise InstallError(f"无法读取镜像信息：{reference}") from exc


def check_image_revision(image_type: str, info: dict[str, Any], source_revision: str) -> None:
    """校验应用镜像标签与离线包声明的源码版本一致。"""
    if image_type not in REVISION_IMAGE_TYPES:
        return
    labels = (info.get("Config") or {}).get("Labels") or {}
    require(isinstance(labels, dict) and labels.get("org.opencontainers.image.revision") == source_revision, f"{image_type} 镜像源码 revision 与离线包不一致")


def image_id_matches_manifest(info: dict[str, Any], entry: dict[str, Any]) -> bool:
    """兼容 daemon image ID 与归档 config digest 两种身份。"""
    expected = {entry.get("image_id"), entry.get("config_digest")} - {None}
    return info.get("Id") in expected


def check_platform() -> None:
    """确认系统运行在 Linux ARM64。"""
    require(sys.platform.startswith("linux"), "安装器仅支持 Linux ARM64 主机")
    require(platform.machine().lower() in {"aarch64", "arm64"}, f"主机架构必须为 ARM64，检测到 {platform.machine()}")


def check_docker() -> None:
    """确认 Docker daemon API、平台及 Compose 满足冻结生产拓扑。"""
    api_version = run(["docker", "version", "--format", "{{.Server.APIVersion}}"], capture=True).stdout.strip()
    api_match = re.fullmatch(r"(\d+)\.(\d+)", api_version)
    require(api_match is not None, f"无法识别 Docker daemon API 版本：{api_version}")
    api_parts = tuple(int(part) for part in api_match.groups())
    require(api_parts >= (1, 48), f"Docker Engine API 至少需要 1.48（gw_priority），检测到 server API {api_version}；请使用 Docker Engine 28.0 或更新版本")
    info = run(["docker", "info", "--format", "{{.OSType}} {{.Architecture}}"], capture=True).stdout.strip().lower()
    require(info.startswith("linux ") and info.split()[-1] in {"aarch64", "arm64"}, f"Docker daemon 必须为 Linux ARM64，检测到 {info}")
    version = run(["docker", "compose", "version", "--short"], capture=True).stdout.strip()
    match = re.search(r"(?:^|v)(\d+)\.(\d+)\.(\d+)", version)
    require(match is not None, f"无法识别 Docker Compose 版本：{version}")
    parts = tuple(int(part) for part in match.groups())
    require(parts >= (2, 33, 1), f"Docker Compose 版本至少需要 2.33.1（生产 Compose 使用 gw_priority），检测到 {version}")


def check_project_unused(project: str) -> None:
    """拒绝复用已存在的 Compose project 资源。"""
    for kind, filters in (
        ("container", ["container", "ls", "-aq", "--filter", f"label=com.docker.compose.project={project}"]),
        ("network", ["network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]),
        ("volume", ["volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]),
    ):
        result = run(["docker", *filters], capture=True)
        require(not result.stdout.strip(), f"Docker 中已经存在 {project} 的 {kind}，拒绝覆盖")


def check_port(port: int) -> None:
    """确认 Web 端口当前可绑定。"""
    require(1 <= port <= 65535, "Web 端口范围必须是 1–65535")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError as exc:
            raise InstallError(f"Web 端口 {port} 已被占用") from exc


def check_destination_unused(destination: Path) -> None:
    """拒绝把部署写入已有目录、文件或符号链接。"""
    require(not destination.exists() and not destination.is_symlink(), f"目标目录已存在，拒绝覆盖：{destination}")


def resolve_new_destination(destination: Path) -> Path:
    """先拒绝目标路径本身的符号链接，再解析其父目录。"""
    check_destination_unused(destination)
    return destination.resolve()


def make_env(destination: Path, port: int, project: str, image_by_type: dict[str, str]) -> str:
    """生成独立的新部署凭据和绝对宿主路径。"""
    secret = lambda size=48: secrets.token_urlsafe(size)
    return "\n".join(
        [
            f"COMPOSE_PROJECT_NAME={project}",
            f"YUXI_STATE_DIR={destination / 'state'}",
            f"YUXI_INSTALL_DIR={destination}",
            f"YUXI_WEB_PORT={port}",
            f"YUXI_VERSION=offline-arm64",
            f"SANDBOX_IMAGE={image_by_type['sandbox']}",
            f"SANDBOX_ENV_FILE={destination / 'sandbox.env'}",
            f"SANDBOX_DOCKER_USER_DATA_HOST_PATH={destination / 'state' / 'yuxi' / 'threads'}",
            f"SANDBOX_DOCKER_SKILL_PROJECTIONS_HOST_PATH={destination / 'state' / 'yuxi' / 'skill-projections'}",
            f"JWT_SECRET_KEY={secret()}",
            f"API_KEY_DERIVATION_SECRET={secret()}",
            f"YUXI_INSTANCE_ID={secrets.token_hex(16)}",
            f"POSTGRES_PASSWORD={secret()}",
            f"NEO4J_PASSWORD={secret()}",
            f"SANDBOX_PROVISIONER_TOKEN={secret()}",
            f"MINIO_ACCESS_KEY={secrets.token_hex(12)}",
            f"MINIO_SECRET_KEY={secret()}",
            "POSTGRES_USER=postgres",
            "POSTGRES_DB=yuxi",
            "NEO4J_USERNAME=neo4j",
            "YUXI_ENV=production",
            "SANDBOX_PROVIDER=provisioner",
            "SANDBOX_RUNTIME_PROFILE=core",
            "",
        ]
    )


def bootstrap_admin(base_url: str) -> str:
    """通过正式初始化接口创建本次部署的首个超级管理员。"""
    uid = input("初始超级管理员 ID（3–20 位字母、数字或下划线）: ").strip()
    require(re.fullmatch(r"[A-Za-z0-9_]{3,20}", uid) is not None, "管理员 ID 格式无效")
    password = getpass.getpass("初始超级管理员密码（至少 8 位）: ")
    confirmation = getpass.getpass("再次输入密码: ")
    require(len(password) >= 8 and password == confirmation, "密码长度不足或两次输入不一致")
    payload = json.dumps({"uid": uid, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        base_url + "/api/auth/initialize", data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            require(200 <= response.status < 300, f"管理员初始化失败：HTTP {response.status}")
            response.read()
    except urllib.error.HTTPError as exc:
        raise InstallError(f"管理员初始化失败：HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except OSError as exc:
        raise InstallError(f"无法完成管理员初始化：{exc}") from exc
    return uid


def wait_ready(base_url: str, timeout: int = 900) -> None:
    """等待 API 的正式 readiness 路由可用。"""
    deadline = time.monotonic() + timeout
    last_error = "尚未响应"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/api/system/ready", timeout=4) as response:
                if response.status == 200:
                    payload = json.loads(response.read())
                    if payload.get("status") == "ready":
                        return
                    last_error = "API 尚未报告 ready"
        except (OSError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(3)
    raise InstallError(f"等待系统 readiness 超时：{last_error}")


def install(bundle: Path, destination: Path, port: int) -> None:
    """验证离线包后在空目录安装并初始化管理员。"""
    check_platform()
    manifest, archives = load_manifest(bundle)
    require((bundle / "compose.yaml").is_file(), "缺少冻结后的 compose.yaml")
    require((bundle / "sandbox.env").is_file(), "缺少 sandbox.env")
    check_docker()
    check_destination_unused(destination)
    project = "smartstaff-offline-" + secrets.token_hex(4)
    check_project_unused(project)
    check_port(port)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    try:
        for name in manifest["components"]:
            source = bundle / name
            shutil.copy2(source, destination / name)
        shutil.copy2(bundle / "manifest.json", destination / "manifest.json")
        (destination / "state").mkdir(mode=0o700)
        image_by_type: dict[str, str] = {}
        for entry, archive in archives:
            run(["docker", "image", "load", "--input", str(archive)])
            info = docker_inspect(entry["reference"])
            require(image_id_matches_manifest(info, entry), f"导入镜像 ID 不符：{entry['reference']}")
            require(info.get("Os") == "linux" and info.get("Architecture") == "arm64", f"导入镜像不是 linux/arm64：{entry['reference']}")
            check_image_revision(entry["type"], info, manifest["source_revision"])
            image_by_type[entry["type"]] = entry["reference"]

        prepare_state_directories(destination / "state", image_by_type)

        env_path = destination / ".env"
        env_path.write_text(make_env(destination, port, project, image_by_type), encoding="utf-8")
        os.chmod(env_path, 0o600)
        os.chmod(destination / "sandbox.env", 0o600)
        run(["docker", "compose", "-p", project, "-f", "compose.yaml", "up", "-d", "--no-build", "--pull", "never"], cwd=destination)
        base_url = f"http://127.0.0.1:{port}"
        wait_ready(base_url)
        uid = bootstrap_admin(base_url)
        print(f"安装完成。管理员 ID：{uid}；访问地址：{base_url}")
        print(f"部署目录：{destination}（凭据保存在权限为 0600 的 .env）")
        print("运行 python3 verify.py 检查部署和沙盒离线依赖。")
    except Exception:
        print(f"安装未完成，目录和已导入镜像保留以便诊断：{destination}", file=sys.stderr)
        raise


def prepare_state_directories(state: Path, images: dict[str, str]) -> None:
    """建立全新存储目录并按镜像运行用户设置属主。"""
    owners = {
        "yuxi/threads": (1000, 1000, "api"),
        "yuxi/skill-sources": (1000, 1000, "api"),
        "yuxi/skill-projections": (1000, 1000, "api"),
        "neo4j/data": (7474, 7474, "neo4j"),
        "neo4j/logs": (7474, 7474, "neo4j"),
        "postgresql": (999, 999, "postgres"),
        "redis": (999, 999, "redis"),
    }
    for relative, (uid, gid, image_type) in owners.items():
        path = state / relative
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        run(
            [
                "docker", "run", "--rm", "--network", "none", "--volume", f"{path}:/data:rw",
                "--user", "0:0", "--entrypoint", "chown", images[image_type], f"{uid}:{gid}", "/data",
            ]
        )


def main() -> int:
    """解析安装参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--target", type=Path, default=Path("/opt/smartstaff-offline"))
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    try:
        target = resolve_new_destination(args.target.expanduser())
        install(args.bundle.resolve(), target, args.port)
    except (InstallError, OSError, subprocess.SubprocessError) as exc:
        print(f"安装失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
