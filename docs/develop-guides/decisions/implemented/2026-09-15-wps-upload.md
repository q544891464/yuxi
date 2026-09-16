# WPS 文档上传与解析

状态：implemented
类型：feature
Owner：backend/package/yuxi/knowledge/parser/capabilities.py

## 问题

知识库格式白名单和 Agent 文档识别未包含 .wps，上传或读取无法进入 Office 解析链路。

## 决策

将 .wps 声明为 Office 输入，复用现有 LibreOffice 转 DOCX 和统一正文表格解析，不改原文件、不放宽大小或权限限制。上传弹窗默认后缀同步支持 .wps。不新增转换服务，也不承诺所有历史专有 WPS 格式兼容。

## 替代方案

仅放开后缀不能完成正文读取；要求用户手动另存 DOCX 增加操作。采用现有转换器，不能转换的文档明确报错。此次不扩大预览格式范围。原件下载继续使用 application/octet-stream 和原文件名，不为内部编码可能不同的 WPS 文件新增 MIME 声明；下载 MIME 调整不属于本次上传与解析范围。

## 后果

WPS 继续使用现有 Office 转换依赖和超时，转换结果校验后才进入解析。不同年代的专有 WPS 格式需要实际样本验证，不能仅凭后缀保证兼容。

## 验证

隔离 Linux 容器相关测试 110 passed，覆盖格式发现、Agent 文档分流、转换失败与临时目录清理，以及真实 LibreOffice 的 DOC/WPS 正文和表格解析、工具生成 Markdown、原件哈希不变。首轮有一项共享技能投影目录权限错误，补充隔离 tmpfs 后通过。

WPS 集成夹具是 DOC 兼容二进制内容的 .wps 文件，不冒充历史 WPS 专有格式；尚无用户原始 WPS 样本，未验证其具体版本。

前端 lint、构建及上传相关单测 4/4 通过。Playwright 在本地应用挂载真实上传弹窗，确认文件选择器 accept 和支持格式提示包含 .wps；该页面没有真实登录和后端，不能作为上传 HTTP 全链路证据。完整前端单测未通过（api_boundary 测试文件失败）。工程契约检查通过；Windows 契约单测仍有符号链接权限和路径分隔符两项环境问题。本机没有 Docker 命令，完整 Compose 后端单测未执行，以上后端测试在独立 Linux 容器执行。
