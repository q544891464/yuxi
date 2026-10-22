# Yuxi Basic Linux ARM64 离线安装包

目标服务器只需 Docker Engine、Docker Compose 和完整离线包。安装过程不构建、不拉取镜像，不使用代理，不读取或迁移已有业务数据、账号和设置；它会创建全新状态、生成随机凭据，并通过产品初始化接口交互式创建首个超级管理员。生产拓扑以仓库根目录 `docker-compose.prod.yml` 为准。

## 在全新服务器安装

将发布人员准备好的离线包复制到 Linux 服务器的数据盘，例如 `/srv/yuxi/offline-bundle`。目标部署目录必须不存在：

```bash
cd /srv/yuxi/offline-bundle
python3 install.py --bundle . --target /srv/yuxi/basic --port 18080
```

安装器要求主机和 Docker daemon 都是 Linux ARM64，Docker Engine server API 至少为 1.48（Docker Engine 28.0+），Docker Compose 至少为 2.33.1（生产 Compose 使用 `gw_priority`），并检查 Compose project 名和 Web 端口未占用。它检查 daemon 报告的 server API，而非客户端协商版本。从[官方 Engine API 版本表](https://docs.docker.com/reference/api/engine/)可见 Engine 28.0 对应 API 1.48；[Compose 服务文档](https://docs.docker.com/reference/compose-file/services/)注明 `gw_priority` 需要 Compose 2.33.1+。安装器不会升级主机 Docker。

若发布包附带 `tools/docker-compose-linux-aarch64`，但服务器 Compose 版本过旧，可由管理员手动安装该插件。先确认发布包外层 `SHA256SUMS` 校验通过，并备份原有插件；以下命令为当前用户安装，执行后检查版本：

```bash
mkdir -p "${DOCKER_CONFIG:-$HOME/.docker}/cli-plugins"
cp "tools/docker-compose-linux-aarch64" "${DOCKER_CONFIG:-$HOME/.docker}/cli-plugins/docker-compose"
chmod +x "${DOCKER_CONFIG:-$HOME/.docker}/cli-plugins/docker-compose"
docker compose version
```

也可由管理员将文件安装到 `/usr/local/lib/docker/cli-plugins/docker-compose` 供所有用户使用。手动替换系统已有插件前，先备份旧文件；安装器本身不替换 Docker CLI 插件。若不使用附带插件，请按服务器发行版的官方 Docker 文档更新 Compose。

安装器从离线归档加载镜像，不运行 `docker build` 或 `docker pull`。部署目录中的 `.env` 权限为 `0600`，包含新部署的随机凭据和沙盒所需绝对宿主路径；`sandbox.env` 是不含凭据的模板。状态保存在部署目录的 `state/`。

安装完成后回读部署事实：

```bash
cd /srv/yuxi/basic
python3 verify.py
```

验证器检查全部文件摘要、镜像 ID 与源码 revision 标签、Compose 离线策略、仅 Web 端口发布、状态挂载边界、长驻和一次性容器状态、`/api/system/ready`，再以 `--network none` 运行沙盒依赖和实际 RapidOCR 权重识别 smoke 检查。

## 发布人员准备离线包

打包机需要 Python 3、PyYAML、Docker CLI/daemon 和已装入的目标 ARM64 镜像。构建源码必须是干净的 Git 提交；四个应用镜像 API、Web、sandbox provisioner 和 Office sandbox runtime 都要带 `org.opencontainers.image.revision=$REV` 标签。以下命令从仓库根目录执行，`$REV` 是完整提交 SHA：

```bash
REV=$(git rev-parse HEAD)
pnpm --dir web install --frozen-lockfile
pnpm --dir web run build

docker buildx build --platform linux/arm64 --load -f docker/api.Dockerfile \
  -t yuxi-api-base:$REV .
docker buildx build --platform linux/arm64 --load \
  --build-arg API_BASE_IMAGE=yuxi-api-base:$REV \
  --label org.opencontainers.image.revision=$REV \
  -f docker/offline/api.Dockerfile -t registry.local/yuxi-api:$REV .
docker buildx build --platform linux/arm64 --load \
  --label org.opencontainers.image.revision=$REV \
  -f docker/sandbox_provisioner/Dockerfile \
  -t registry.local/yuxi-provisioner:$REV docker/sandbox_provisioner
docker buildx build --platform linux/arm64 --load \
  --build-arg SANDBOX_BASE_IMAGE=registry.local/sandbox-base:replace-with-verified-arm64-tag \
  -f docker/sandbox-runtime/Dockerfile -t yuxi-sandbox-runtime:$REV .
docker buildx build --platform linux/arm64 --load \
  --build-arg SANDBOX_RUNTIME_IMAGE=yuxi-sandbox-runtime:$REV \
  --label org.opencontainers.image.revision=$REV \
  -f docker/offline/sandbox.Dockerfile -t registry.local/yuxi-sandbox:$REV .
docker buildx build --platform linux/arm64 --load \
  --build-arg NGINX_IMAGE=registry.local/nginx:replace-with-verified-arm64-tag \
  --label org.opencontainers.image.revision=$REV \
  -f docker/offline/web.Dockerfile -t registry.local/yuxi-web:$REV .
```

`docker/offline/api.Dockerfile` 会把 RapidOCR 权重固化进 API 镜像；`docker/offline/sandbox.Dockerfile` 在 sandbox runtime 上增加离线 Office 依赖；`docker/offline/web.Dockerfile` 使用前面生成的 `web/dist`。将两个 `replace-with-verified-arm64-tag` 标签替换为本次发布已验证并已加载到本地的 ARM64 镜像引用。

准备 JSON，为生产 Compose 的全部服务映射到本地固定 ARM64 镜像。API、worker 和 migrator 共用 API 镜像；同一 image type 必须映射到同一引用。图数据库、向量库、对象存储、PostgreSQL、Redis 和 etcd 使用本次生产 Compose 实际验证的镜像引用，不在此文档固定版本：

```json
{
  "api": "registry.local/yuxi-api:<REV>",
  "worker": "registry.local/yuxi-api:<REV>",
  "storage-migrator": "registry.local/yuxi-api:<REV>",
  "sandbox-runtime-image": "registry.local/yuxi-sandbox:<REV>",
  "sandbox-provisioner": "registry.local/yuxi-provisioner:<REV>",
  "web": "registry.local/yuxi-web:<REV>",
  "graph": "replace-with-verified-arm64-neo4j-reference",
  "etcd": "replace-with-verified-arm64-etcd-reference",
  "minio": "replace-with-verified-arm64-minio-reference",
  "milvus": "replace-with-verified-arm64-milvus-reference",
  "postgres": "replace-with-verified-arm64-postgres-reference",
  "redis": "replace-with-verified-arm64-redis-reference"
}
```

以上内容是占位符，需替换成真实引用。然后打包：

```bash
python3 -m pip install pyyaml
python3 scripts/offline/package.py \
  --image-map /srv/yuxi/image-map.json \
  --source-revision "$REV" \
  --output /srv/yuxi/offline-bundle
```

打包器检查镜像架构、应用镜像 revision 标签、冻结 Compose 和全部只读文件 SHA256，输出十类镜像归档及清单；它还会从归档 Config blob 计算规范 SHA256，安装时以该摘要兼容 containerd manifest ID 与经典 Docker config ID。输出目录必须不存在；发生失败时会删除本次创建的不完整目录。将完整离线包复制到目标服务器。

## 本地逻辑检查

```bash
python3 -m unittest scripts.offline.test_offline
```

测试覆盖归档与组件篡改、平台和清单错误、越界路径、符号链接目标拒绝解析、镜像 revision、健康状态正反例、SystemExit 清理和 Compose 冻结规则。它不替代目标 DGX Spark 的安装、readiness 和断网镜像验证。
