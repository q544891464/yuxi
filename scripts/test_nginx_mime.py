"""使用真实 Nginx 验证前端模块资源的响应类型。"""

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from urllib.request import urlopen


class NginxMimeTest(unittest.TestCase):
    """防止 PDF.js worker 被当作二进制文件发送。"""

    def test_module_worker_is_javascript(self):
        """真实 HTTP 应保留模块字节并返回 JavaScript 类型。"""
        root = Path(__file__).resolve().parents[1]
        module = b"export const previewWorker = true;\n"
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory)
            static.chmod(0o755)
            (static / "worker.mjs").write_bytes(module)
            (static / "worker.mjs").chmod(0o644)
            container = subprocess.check_output(
                [
                    "docker", "run", "-d", "--rm", "--pull=never",
                    "--add-host", "api:127.0.0.1", "--add-host", "minio:127.0.0.1",
                    "-p", "127.0.0.1::80",
                    "-v", f"{root / 'docker/nginx/nginx.conf'}:/etc/nginx/nginx.conf:ro",
                    "-v", f"{root / 'docker/nginx/default.conf'}:/etc/nginx/conf.d/default.conf:ro",
                    "-v", f"{static}:/usr/share/nginx/html:ro",
                    os.environ.get("NGINX_TEST_IMAGE", "nginx:alpine"),
                ], text=True,
            ).strip()
            try:
                port = subprocess.check_output(
                    ["docker", "port", container, "80/tcp"], text=True
                ).strip().rsplit(":", 1)[1]
                for attempt in range(30):
                    try:
                        response = urlopen(f"http://127.0.0.1:{port}/worker.mjs", timeout=2)
                        break
                    except OSError:
                        if attempt == 29:
                            raise
                        time.sleep(0.1)
                with response:
                    self.assertEqual(response.read(), module)
                    self.assertIn(
                        response.headers.get_content_type(),
                        {"application/javascript", "text/javascript"},
                    )
            finally:
                subprocess.run(["docker", "rm", "-f", container], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
