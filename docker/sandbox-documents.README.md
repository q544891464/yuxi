# 办公沙盒镜像

在仓库根构建 `docker build -f docker/sandbox-documents.Dockerfile -t yuxi-sandbox:documents-20260914 .`，下载在执行 Docker 的服务器发生。

将 `-f docker/sandbox-documents.compose.yml` 追加到部署正在使用的完整 Compose 文件序列，再执行 `up -d --no-deps sandbox-provisioner`。后续 Compose 运维必须保留此覆盖文件。新建沙盒使用预装镜像，已运行沙盒仍按原有生命周期清理。

断网验证命令：

```sh
docker run --rm --network none --tmpfs /home/gem:rw,exec,mode=777 --user 1000:1000 -e HOME=/home/gem --entrypoint python3 yuxi-sandbox:documents-20260914 /opt/yuxi-documents-smoke.py
```

使用系统 `python3` 即可导入 `docx`、`docxtpl`、`openpyxl`、`pptx`、`pypdf`、`reportlab`。LibreOffice 与中文字体由镜像提供。独立虚拟环境不会自动继承这些库；只有缺少特殊依赖时才安装。镜像不包含用户文件和用户密钥。
