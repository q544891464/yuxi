# 旧版 Word 文档解析

状态：implemented
类型：bug-fix
Owner：backend/package/yuxi/knowledge/parser/unified.py

## 问题

Agent 文件解析工具接收旧版 `.doc` 后，统一解析器没有对应分支，运行以 Unsupported file type 失败。

## 决策

复用已有 LibreOffice 隔离临时目录与进程超时机制，将 `.doc` 转为 `.docx`，继续使用现有 Word 正文与表格解析。统一格式能力声明加入 `.doc`，转换结果只存在临时目录，不覆盖原文件。保持现有授权下载、Markdown 产物及预览入口。

## 替代方案

要求用户手工另存为 DOCX 无法修复已上传文件的调用；转 PDF 再 OCR 增加服务依赖并可能损失表格结构，因此选择 DOCX 中间格式。

## 后果

LibreOffice 对损坏、加密文件可能转换失败，必须明确报错。转换成功不等于扫描图片已 OCR；本次只修复旧版 Word 格式处理，不改变 OCR 配置与权限。

## 验证

- 隔离 Linux 容器基于线上既有镜像，使用真实 LibreOffice；`python -m pytest test/unit -m "not slow" -q`：2015 passed。
- `python -m pytest --confcutdir=test/integration/services test/integration/services/test_legacy_doc_parser.py -q`：1 passed。该测试不需要数据库或沙盒服务，限定 conftest 范围避免运行全局集成环境清理。真实转换、公开解析服务及工具 Markdown 产物均验证；文件服务下载/上传边界为测试替身，不作为 HTTP/worker/SSE E2E 证据。
- 服务器隔离副本验证已上传 DOC：提取 23621 字符、162 行 Markdown 表格，原文件 SHA-256 未变。未在该隔离环境验证内嵌图片上传，不保存报告内容到仓库。
- `python scripts/verify_engineering_contracts.py` 与 Linux `python -m unittest scripts.test_verify_engineering_contracts`：通过，后者 62 tests。
- 公开支持格式说明、知识库下载 MIME 与前端能力请求失败时的格式列表同步加入 `.doc`。
- 前端 `pnpm run lint:check`、`pnpm run test:unit`（330 passed）通过；本次仅修正上传格式回退值，无页面布局变更。
- 前端与文档 `pnpm run build` 均通过；独立 Reviewer 复审通过，`git diff --check` 无问题。
