#!/usr/bin/env python3
"""只读检查离线部署、镜像架构、端口和沙盒断网运行。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from install import InstallError, check_docker, check_image_revision, image_id_matches_manifest, load_manifest, run


def verify(directory: Path) -> None:
    """检查本机部署事实并运行沙盒 offline smoke。"""
    directory = directory.resolve()
    require_files = ("compose.yaml", "manifest.json", ".env", "sandbox-smoke.py", "ocr-smoke.py", "README.md")
    for name in require_files:
        if not (directory / name).is_file():
            raise InstallError(f"缺少部署文件：{name}")
    env_mode = (directory / ".env").stat().st_mode & 0o777
    if env_mode & 0o077:
        raise InstallError(".env 必须仅允许文件所有者读取和写入（0600）")

    check_docker()
    manifest, images = load_manifest(directory, verify_archives=False)
    for entry, _ in images:
        result = run(["docker", "image", "inspect", entry["reference"]], capture=True)
        info = json.loads(result.stdout)[0]
        if not image_id_matches_manifest(info, entry) or info.get("Os") != "linux" or info.get("Architecture") != "arm64":
            raise InstallError(f"镜像与清单不一致：{entry['reference']}")
        check_image_revision(entry["type"], info, manifest["source_revision"])

    project = read_env(directory / ".env", "COMPOSE_PROJECT_NAME")
    port = int(read_env(directory / ".env", "YUXI_WEB_PORT"))
    config = run(["docker", "compose", "-p", project, "-f", "compose.yaml", "config", "--format", "json"], cwd=directory, capture=True)
    rendered = json.loads(config.stdout)
    services = rendered.get("services", {})
    if {"mineru-api", "paddlex"} & set(services):
        raise InstallError("离线 Basic Compose 包含 GPU OCR 服务")
    if any("build" in service or service.get("pull_policy") != "never" for service in services.values()):
        raise InstallError("Compose 必須禁止构建和拉取镜像")
    published = [name for name, service in services.items() if service.get("ports")]
    if published != ["web"] or services["web"]["ports"][0].get("published") != str(port):
        raise InstallError(f"仅允许 Web 发布端口，实际服务为 {published}")
    root = directory.resolve()
    for service_name, service in services.items():
        for mount in service.get("volumes", []):
            source = mount.get("source") if isinstance(mount, dict) else None
            if source and (Path(source).is_absolute() or str(source).startswith(".")):
                host_path = Path(source).resolve()
                docker_socket = service_name == "sandbox-provisioner" and source == "/var/run/docker.sock"
                if not host_path.is_relative_to(root) and not docker_socket:
                    raise InstallError(f"服务 {service_name} 的宿主挂载越出部署目录：{source}")

    ps = run(["docker", "compose", "-p", project, "-f", "compose.yaml", "ps", "-a", "--format", "json"], cwd=directory, capture=True)
    try:
        parsed_ps = json.loads(ps.stdout)
        rows = parsed_ps if isinstance(parsed_ps, list) else [parsed_ps]
    except ValueError:
        rows = [json.loads(line) for line in ps.stdout.splitlines() if line.strip()]
    expected = set(services)
    actual = {row.get("Service") for row in rows}
    if not expected <= actual:
        raise InstallError(f"Compose 服务尚未全部创建：{sorted(expected - actual)}")
    validate_service_rows(rows, expected)

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/ready", timeout=10) as response:
        readiness = json.loads(response.read())
    if response.status != 200 or readiness.get("status") != "ready":
        raise InstallError("/api/system/ready 未返回 ready")

    sandbox = next(entry["reference"] for entry, _ in images if entry["type"] == "sandbox")
    run(
        [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,exec,mode=1777", "--tmpfs", "/home/gem:rw,exec,mode=777",
            "--user", "1000:1000", "-e", "HOME=/home/gem",
            "--volume", f"{directory / 'sandbox-smoke.py'}:/opt/yuxi-sandbox-smoke.py:ro",
            "--entrypoint", "python3", sandbox, "/opt/yuxi-sandbox-smoke.py",
        ]
    )
    api = next(entry["reference"] for entry, _ in images if entry["type"] == "api")
    run(
        [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,exec,mode=1777", "-e", "YUXI_RUNTIME_DIR=/tmp/ocr-runtime",
            "-e", "HOME=/tmp", "-e", "XDG_CACHE_HOME=/tmp/.cache",
            "--volume", f"{directory / 'ocr-smoke.py'}:/opt/basic-ocr-smoke.py:ro",
            "--entrypoint", "python", api, "/opt/basic-ocr-smoke.py",
        ]
    )
    print(json.dumps({"status": "passed", "platform": manifest["platform"], "services": len(expected), "readiness": readiness["status"], "sandbox_network": "none", "ocr_network": "none"}, ensure_ascii=False))


def validate_service_rows(rows: list[dict], expected: set[str]) -> None:
    """确认全部长驻服务健康，且一次性服务成功退出。"""
    actual = {row.get("Service") for row in rows}
    if not expected <= actual:
        raise InstallError(f"Compose 服务尚未全部创建：{sorted(expected - actual)}")
    for row in rows:
        service_name = row.get("Service")
        state = str(row.get("State", "")).lower()
        if service_name in {"storage-migrator", "sandbox-runtime-image"}:
            if state != "exited" or str(row.get("ExitCode")) != "0":
                raise InstallError(f"一次性服务未成功退出：{service_name} ({state}, {row.get('ExitCode')})")
        else:
            health = str(row.get("Health") or "").strip().lower()
            if state != "running" or (health and health != "healthy"):
                raise InstallError(f"长驻服务没有处于 running/healthy 状态：{service_name} ({state}, {health or 'no healthcheck'})")


def read_env(path: Path, key: str) -> str:
    """读取部署文件中的单个无引号值。"""
    prefix = key + "="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise InstallError(f".env 缺少 {key}")


def main() -> int:
    """执行只读部署验证。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        verify(args.directory)
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"验证失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
