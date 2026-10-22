# 离线办公沙盒运行时

该镜像以 `SANDBOX_RUNTIME_IMAGE` 为基础，保留基础镜像的 PyMySQL、MarkItDown、Tesseract 中文/英文语言包和 .NET SDK，再增加 LibreOffice、Noto CJK 字体、Poppler 与固定版本的 Python/Node 办公库。镜像不复制业务文件、账号或持久化数据。

从仓库根目录构建；构建节点需要能够拉取基础镜像并访问 apt、PyPI、npm 和 NuGet 包源。运行容器本身可断网使用：Node 包安装在 `/opt/yuxi-node/node_modules`，`NODE_PATH` 和 `PATH` 已配置；Python 包安装到系统 Python；NuGet 的 `DocumentFormat.OpenXml` 3.3.0 包缓存在 `/opt/yuxi-nuget`。

```sh
docker build -f docker/offline/sandbox.Dockerfile \
  --build-arg SANDBOX_RUNTIME_IMAGE=yuxi-sandbox-runtime:arm64 \
  -t yuxi-sandbox:offline-office .
docker run --rm --network none --read-only --tmpfs /tmp:rw,exec,mode=1777 \
  --user 1000:1000 --entrypoint python3 yuxi-sandbox:offline-office \
  /opt/yuxi-sandbox-smoke.py
```

Smoke 脚本只在 `/tmp` 创建临时样例，检查 Python 与 Node 生成/回读 DOCX、XLSX、PPTX、PDF，LibreOffice 中文转 PDF、Poppler、Tesseract OCR，以及预缓存时的 .NET 离线 NuGet restore 和 OpenXML DOCX 生成。成功只输出一行 JSON；缺少强制依赖或产物不正确时以非零退出码结束。`dotnet_openxml_offline` 为 `false` 表示包缓存未随镜像提供。

`python-docx`、`docxtpl`、`pypdf` 和 `reportlab` 沿用既有办公镜像固定版本。基础 runtime 保留 PyMySQL、MarkItDown[pptx]、Tesseract eng/chi_sim 和 .NET 8.0.425；办公层补充 pandas、openpyxl、python-pptx、Pillow、matplotlib、XlsxWriter、xlrd、pypdfium2、pdfplumber，并提供 npm `docx`、`pptxgenjs`、`xlsx`。
