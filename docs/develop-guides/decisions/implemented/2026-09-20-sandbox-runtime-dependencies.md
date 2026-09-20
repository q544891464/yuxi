# Agent 沙盒预装通用联网依赖

状态：implemented
类型：feature
Owner：docker/sandbox-runtime/Dockerfile

## 问题

Agent 在首次处理 MySQL、OCR、PPTX 或 .NET 文档任务时临时联网安装依赖，浪费对话时间，并在运行期网络受限时直接失败。API/worker 已安装的 Python 包不会自动出现在独立沙盒容器中。

## 决策

基于当前受支持的 all-in-one sandbox 镜像构建 Yuxi 自有 runtime 镜像，预装 PyMySQL、MarkItDown PPTX 支持、Tesseract 中英文 OCR 和 .NET 8 SDK。Compose provisioner 默认创建该镜像的沙盒，安装脚本预先构建它。

密钥和数据库地址不写入镜像；`SILICONFLOW_API_KEY` 与 `MYSQL_*` 继续通过用户 Agent 环境配置注入。NuGet 项目专属包仍由对应 Skill 的项目锁文件决定，镜像只预装 SDK，避免缓存一个不可审计的浮动依赖集合。

## 替代方案

- 在 API 镜像安装：Agent 命令运行在独立沙盒中，无法使用，拒绝。
- 每次任务动态安装：正是当前延迟和失败来源，拒绝。
- 把密钥固化进镜像：泄露凭据且无法按用户隔离，拒绝。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| 新沙盒无需联网安装即可导入 PyMySQL/MarkItDown | 依赖装到错误容器 | runtime image | `test_sandbox_runtime_image.py` 与待执行容器 import probe | 镜像契约缺包时 unit 失败 | 契约通过；真实镜像待 Linux Docker 验证 |
| 新沙盒可直接运行中英文 OCR 与 dotnet | 二进制或语言包缺失 | runtime image | `test_sandbox_runtime_image.py`、待执行 `tesseract --list-langs` 与 `dotnet --info` | 缺安装声明时 unit 失败 | 契约通过；真实二进制待 Linux Docker 验证 |
| Compose provisioner 使用自有 runtime 镜像 | 镜像构建了但未装配 | compose + provisioner env | Compose 解析契约 | provisioner 缺少 build service 依赖时 unit 失败 | 通过 |

## 后果

首次构建和镜像体积增加，换取任务运行期更低延迟和不依赖临时下载。新增通用依赖需要通过 Dockerfile Review，而不是由对话静默污染运行环境。
