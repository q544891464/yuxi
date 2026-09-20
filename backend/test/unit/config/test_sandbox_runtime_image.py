from pathlib import Path

import pytest
import yaml


def _project_root() -> Path:
    """定位包含沙盒运行时定义的仓库根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "docker/sandbox-runtime/Dockerfile").exists():
            return parent
    pytest.skip("当前测试环境未挂载仓库根目录")


def _load_compose(filename: str) -> dict:
    """读取未插值的 Compose 契约。"""
    return yaml.safe_load((_project_root() / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "default_image"),
    [
        ("docker-compose.yml", "${COMPOSE_PROJECT_NAME:-yuxi}-agent-sandbox:${YUXI_VERSION:-0.7.3}"),
        ("docker-compose.prod.yml", "yuxi-agent-sandbox:${YUXI_VERSION:-0.7.3}"),
    ],
)
def test_compose_builds_and_uses_default_runtime(
    filename: str,
    default_image: str,
) -> None:
    compose = _load_compose(filename)
    services = compose["services"]
    runtime = services["sandbox-runtime-image"]
    provisioner = services["sandbox-provisioner"]

    expected_base_image = (
        "${SANDBOX_IMAGE:-enterprise-public-cn-beijing.cr.volces.com/"
        "vefaas-public/all-in-one-sandbox:1.11.0}"
    )
    assert runtime["build"] == {
        "context": "./docker/sandbox-runtime",
        "dockerfile": "Dockerfile",
        "args": {"SANDBOX_BASE_IMAGE": expected_base_image},
    }
    assert runtime["image"] == default_image
    provisioner_image = next(
        item.removeprefix("SANDBOX_IMAGE=") for item in provisioner["environment"] if item.startswith("SANDBOX_IMAGE=")
    )
    assert provisioner_image == f"${{SANDBOX_IMAGE:-{default_image}}}"
    assert provisioner["depends_on"]["sandbox-runtime-image"] == {"condition": "service_completed_successfully"}


def test_runtime_preinstalls_common_agent_dependencies_without_credentials() -> None:
    root = _project_root()
    dockerfile = (root / "docker/sandbox-runtime/Dockerfile").read_text(encoding="utf-8")
    requirements = (root / "docker/sandbox-runtime/requirements.txt").read_text(encoding="utf-8")
    runtime_contract = f"{dockerfile}\n{requirements}"

    for marker in (
        "PyMySQL==1.2.0",
        "markitdown[pptx]==0.1.7",
        "tesseract-ocr",
        "tesseract-ocr-chi-sim",
        "tesseract-ocr-eng",
        "DOTNET_SDK_VERSION=8.0.425",
        'dotnet-install.sh --version "$DOTNET_SDK_VERSION"',
    ):
        assert marker in runtime_contract

    for secret_name in (
        "SILICONFLOW_API_KEY",
        "MYSQL_HOST",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
    ):
        assert secret_name not in runtime_contract


def test_initializers_skip_default_runtime_build_for_custom_image() -> None:
    root = _project_root()
    shell_script = (root / "scripts/init.sh").read_text(encoding="utf-8")
    powershell_script = (root / "scripts/init.ps1").read_text(encoding="utf-8")

    assert 'configured_sandbox_image="${SANDBOX_IMAGE:-$(get_env_value SANDBOX_IMAGE)}"' in shell_script
    assert '$configuredSandboxImage = if ($env:SANDBOX_IMAGE)' in powershell_script
    assert "skipping the default Agent runtime build" in shell_script
    assert "skipping the default Agent runtime build" in powershell_script
