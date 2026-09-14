# 沙盒办公依赖预装

状态：implemented
类型：feature
Owner：docker/sandbox-documents.Dockerfile

## 问题

临时沙盒清理导致对话重复安装 Word 和 Office 转换依赖；历史工具记录中 Word 依赖和 Office 转换频繁出现。

## 决策

固定基础镜像 digest，使用派生镜像预装 Word、PDF、Office 转换和中文字体；保留基础镜像现有表格、绘图、幻灯片库。通过 provisioner 已有 SANDBOX_IMAGE 配置选择，新建沙盒生效。构建与使用命令由 docker/sandbox-documents.README.md 维护，smoke 脚本拥有文件生成和回读验证。

## 替代方案

持久化整个用户环境会混合文件与执行环境生命周期；每次启动安装仍需网络并增加延迟。镜像预装将下载成本移到部署时。

## 后果

镜像体积增加；特殊依赖仍按需安装。现有运行不强制中断，后续新建沙盒使用新镜像。独立虚拟环境不自动继承系统库。

## 验证

服务器构建通过；断网、临时 /home/gem、UID 1000 下生成并回读中文 DOCX、XLSX、PPTX、PDF 和 Word 转 PDF 通过。原镜像 import docx 失败，构成缺包负控。真实 provisioner HTTP 创建临时沙盒后以 UID 1000 执行同一文件探针通过，探针沙盒已删除。未执行真实大模型整段对话，因此不保证模型绝不主动尝试安装。Windows verifier 单元测试存在符号链接权限与路径分隔符两个环境失败；本机未安装 Docker，无法执行完整后端单测。
