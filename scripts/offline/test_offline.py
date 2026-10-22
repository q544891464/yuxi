"""离线包清单、目标目录和 Compose 变换的负向/正向检查。"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = ROOT / "output" / "test-tmp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def load_module(name: str, path: Path):
    """从离线脚本路径加载模块。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


installer = load_module("offline_install", Path(__file__).with_name("install.py"))
packager = load_module("offline_package", Path(__file__).with_name("package.py"))
with mock.patch.dict(sys.modules, {"install": installer}):
    verifier = load_module("offline_verify", Path(__file__).with_name("verify.py"))


class OfflineInstallTests(unittest.TestCase):
    """验证离线部署关键拒绝条件。"""

    def _bundle(self, root: Path) -> Path:
        bundle = root / "bundle"
        (bundle / "images").mkdir(parents=True)
        entries = []
        for image_type in sorted(installer.IMAGE_TYPES):
            archive = f"images/{image_type}.tar.gz"
            file_path = bundle / archive
            file_path.write_bytes(image_type.encode())
            reference = f"basic-offline/{image_type}:abc-arm64"
            entries.append({
                "type": image_type,
                "reference": reference,
                "image_id": "sha256:" + hashlib.sha256(reference.encode()).hexdigest(),
                "config_digest": "sha256:" + hashlib.sha256((reference + "-config").encode()).hexdigest(),
                "architecture": "arm64",
                "archive": archive,
                "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
            })
        components = {}
        for name in packager.REQUIRED_COMPONENTS:
            component = bundle / name
            component.write_text("test component\n", encoding="utf-8")
            components[name] = hashlib.sha256(component.read_bytes()).hexdigest()
        (bundle / "manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "platform": "linux/arm64",
            "source_revision": "a" * 40,
            "components": components,
            "images": entries,
        }), encoding="utf-8")
        return bundle

    def test_changed_archive_hash_is_rejected_before_image_load(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            (bundle / "images" / "api.tar.gz").write_bytes(b"changed")
            with self.assertRaisesRegex(installer.InstallError, "SHA256 不匹配"):
                installer.load_manifest(bundle)

    def test_non_arm64_manifest_is_rejected_before_image_load(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            data = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            data["images"][0]["architecture"] = "amd64"
            (bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "架构不是 arm64"):
                installer.load_manifest(bundle)

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            target = Path(temporary) / "already-used"
            target.mkdir()
            marker = target / "keep.txt"
            marker.write_text("existing state", encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "拒绝覆盖"):
                installer.check_destination_unused(target)
            self.assertEqual(marker.read_text(encoding="utf-8"), "existing state")

    def test_component_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            (bundle / "compose.yaml").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "组件 SHA256 不匹配"):
                installer.load_manifest(bundle)

    def test_manifest_must_hash_every_readonly_component(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            manifest_path = bundle / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            del data["components"]["README.md"]
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "全部只读部署组件"):
                installer.load_manifest(bundle)

    def test_archive_path_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            bundle = self._bundle(root)
            data = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            data["images"][0]["archive"] = "images/../../outside.tar.gz"
            (bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "归档路径必须位于 images"):
                installer.load_manifest(bundle)

    def test_malformed_manifest_root_is_rejected_cleanly(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            (bundle / "manifest.json").write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "必须是 JSON 对象"):
                installer.load_manifest(bundle)

    def test_duplicate_manifest_image_type_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            bundle = self._bundle(Path(temporary))
            data = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            data["images"][1]["type"] = data["images"][0]["type"]
            (bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(installer.InstallError, "恰好包含十种 Basic 镜像"):
                installer.load_manifest(bundle)

    def test_dangling_symlink_target_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            link_target = root / "deployment-link"
            with mock.patch.object(Path, "is_symlink", return_value=True), mock.patch.object(Path, "resolve") as resolve:
                with self.assertRaisesRegex(installer.InstallError, "拒绝覆盖"):
                    installer.resolve_new_destination(link_target)
            resolve.assert_not_called()

    def test_fresh_env_has_sandbox_paths_and_minio_secrets(self):
        target = Path("/srv/yuxi/basic")
        values = {
            "sandbox": "basic-offline/sandbox:abc-arm64",
        }
        content = installer.make_env(target, 18080, "project", values)
        self.assertIn(f"SANDBOX_DOCKER_USER_DATA_HOST_PATH={target / 'state' / 'yuxi' / 'threads'}", content)
        self.assertIn(f"SANDBOX_DOCKER_SKILL_PROJECTIONS_HOST_PATH={target / 'state' / 'yuxi' / 'skill-projections'}", content)
        self.assertIn("MINIO_ACCESS_KEY=", content)
        self.assertIn("MINIO_SECRET_KEY=", content)

    def test_docker_requires_server_api_148_for_gw_priority(self):
        def completed(stdout):
            return subprocess.CompletedProcess([], 0, stdout, "")

        with mock.patch.object(installer, "run", side_effect=[completed("1.48\n"), completed("linux aarch64\n"), completed("v2.33.1\n")]) as mocked:
            installer.check_docker()
        self.assertEqual(mocked.call_args_list[0].args[0], ["docker", "version", "--format", "{{.Server.APIVersion}}"])

        with mock.patch.object(installer, "run", return_value=completed("1.47\n")):
            with self.assertRaisesRegex(installer.InstallError, "server API 1.47"):
                installer.check_docker()

    def test_docker_rejects_unparseable_server_api(self):
        with mock.patch.object(installer, "run", return_value=subprocess.CompletedProcess([], 0, "unknown\n", "")):
            with self.assertRaisesRegex(installer.InstallError, "无法识别 Docker daemon API"):
                installer.check_docker()

    def test_compose_removes_gpu_ocr_build_and_non_web_host_ports(self):
        services = {
            name: {"image": name + ":old", "build": {"context": "."}, "ports": ["9000:9000"]}
            for name in packager.SERVICE_TYPE
        }
        services.update({"mineru-api": {"build": {"context": "."}}, "paddlex": {"build": {"context": "."}}})
        image_map = {name: f"basic-offline/{packager.SERVICE_TYPE[name]}:abc-arm64" for name in packager.SERVICE_TYPE}
        frozen = packager.rewrite_compose({"services": services}, image_map)
        self.assertNotIn("mineru-api", frozen["services"])
        self.assertNotIn("paddlex", frozen["services"])
        self.assertEqual(set(frozen["services"]["web"]["ports"]), {"${YUXI_WEB_PORT:-18080}:80"})
        self.assertTrue(all("build" not in service and service["pull_policy"] == "never" for service in frozen["services"].values()))
        for name in ("api", "worker", "storage-migrator"):
            self.assertIn("MINIO_ACCESS_KEY", frozen["services"][name]["environment"])
            self.assertIn("MINIO_SECRET_KEY", frozen["services"][name]["environment"])

    def test_healthy_services_and_successful_one_shots_pass_verifier(self):
        expected = set(packager.SERVICE_TYPE)
        rows = [
            {"Service": name, "State": "running", "Health": "healthy"}
            for name in expected - {"storage-migrator", "sandbox-runtime-image"}
        ]
        rows.extend([
            {"Service": "storage-migrator", "State": "exited", "ExitCode": 0},
            {"Service": "sandbox-runtime-image", "State": "exited", "ExitCode": 0},
        ])
        verifier.validate_service_rows(rows, expected)

    def test_failed_long_running_service_is_rejected_by_verifier(self):
        expected = set(packager.SERVICE_TYPE)
        rows = [
            {"Service": name, "State": "running", "Health": "healthy"}
            for name in expected - {"storage-migrator", "sandbox-runtime-image"}
        ]
        rows.extend([
            {"Service": "storage-migrator", "State": "exited", "ExitCode": 0},
            {"Service": "sandbox-runtime-image", "State": "exited", "ExitCode": 0},
        ])
        next(row for row in rows if row["Service"] == "worker")["Health"] = "unhealthy"
        with self.assertRaisesRegex(installer.InstallError, "没有处于 running/healthy"):
            verifier.validate_service_rows(rows, expected)

    def test_core_image_revision_label_must_match_declared_source(self):
        revision = "a" * 40
        info = {"Config": {"Labels": {"org.opencontainers.image.revision": revision}}}
        packager.validate_image_revision("api", info, revision)
        with self.assertRaisesRegex(SystemExit, "revision 标签"):
            packager.validate_image_revision("api", {"Config": {"Labels": {}}}, revision)

    def test_image_identity_accepts_daemon_id_or_archive_config_digest(self):
        entry = {"image_id": "sha256:" + "a" * 64, "config_digest": "sha256:" + "b" * 64}
        self.assertTrue(installer.image_id_matches_manifest({"Id": entry["image_id"]}, entry))
        self.assertTrue(installer.image_id_matches_manifest({"Id": entry["config_digest"]}, entry))
        self.assertFalse(installer.image_id_matches_manifest({"Id": "sha256:" + "c" * 64}, entry))

    def test_archive_config_digest_matches_actual_config_blob(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            archive_path = Path(temporary) / "image.tar.gz"
            reference = "local.invalid/yuxi-api:test"
            config = b'{"architecture":"arm64","os":"linux"}'
            config_path = "blobs/sha256/config.json"
            rows = [
                ("manifest.json", json.dumps([{"Config": config_path, "RepoTags": [reference]}]).encode()),
                (config_path, config),
            ]
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, contents in rows:
                    member = tarfile.TarInfo(name)
                    member.size = len(contents)
                    archive.addfile(member, io.BytesIO(contents))
            expected = "sha256:" + hashlib.sha256(config).hexdigest()
            self.assertEqual(packager.archive_config_digest(archive_path, reference), expected)

    def test_archive_config_path_cannot_escape_tar_root(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            archive_path = Path(temporary) / "image.tar.gz"
            reference = "local.invalid/yuxi-api:test"
            rows = [{"Config": "../outside.json", "RepoTags": [reference]}]
            with tarfile.open(archive_path, "w:gz") as archive:
                contents = json.dumps(rows).encode()
                member = tarfile.TarInfo("manifest.json")
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
            with self.assertRaisesRegex(SystemExit, "Config 路径无效"):
                packager.archive_config_digest(archive_path, reference)

    def test_system_exit_during_image_validation_removes_partial_output(self):
        try:
            import yaml
        except ImportError:
            self.fail("PyYAML is required by the packager and its focused test")
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            compose = root / "compose.yaml"
            image_map = root / "image-map.json"
            output = root / "bundle"
            services = {name: {} for name in packager.SERVICE_TYPE}
            services.update({"mineru-api": {}, "paddlex": {}})
            compose.write_text(yaml.safe_dump({"services": services}), encoding="utf-8")
            refs = {name: f"local.invalid/{packager.SERVICE_TYPE[name]}:arm64" for name in packager.SERVICE_TYPE}
            image_map.write_text(json.dumps(refs), encoding="utf-8")
            with mock.patch.object(packager, "resolve_source_revision", return_value="a" * 40), mock.patch.object(
                packager, "docker_json", return_value={"Os": "linux", "Architecture": "amd64"}
            ):
                with self.assertRaises(SystemExit):
                    packager.build_bundle(compose, image_map, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
