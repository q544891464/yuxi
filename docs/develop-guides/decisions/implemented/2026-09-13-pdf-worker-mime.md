# PDF 预览模块的响应类型

状态：implemented
类型：bug-fix
Owner：docker/nginx/nginx.conf

## 问题

生产 Nginx 的默认 MIME 表未识别 `.mjs`，PDF.js worker 返回 `application/octet-stream`，浏览器拒绝导入。DOCX 转换后的 PDF 因而显示加载失败。

## 决策

在 Nginx HTTP 层补充 `.mjs` 的 JavaScript MIME 映射，保留既有 MIME 表、资源路径和预览链路。这是已复现且无待裁决取舍的局部修复，直接记录为 implemented。

`web/src/components/common/PdfPreview.vue` 通过 Vite 的 `?worker&url` 构建 PDF.js worker，生成带内容哈希的 `.js` 资源。仅修改响应类型不足以更新旧浏览器缓存：资源字节未改变时，原 `.mjs` 地址仍可能返回无 Content-Type 的 304，使浏览器继续使用旧二进制类型。新的 worker 构建地址切断该旧缓存引用，不要求用户清除浏览器缓存。

## 替代方案

改写 PDF.js worker 文件扩展名会使构建配置依赖具体包产物；修改 DOCX 转换器无法解决浏览器拒绝模块的问题。

直接附加固定查询参数也能更换缓存地址，但 worker 应由 Vite 的标准 worker 构建入口拥有，不引入一次性的版本参数。

## 后果

ES module 静态资源使用浏览器认可的类型。文件授权、转换缓存及原始文件均不改变。

## 验证

`python3 scripts/test_nginx_mime.py` 使用真实 Nginx 和 HTTP，验证模块字节及 JavaScript 响应类型；旧配置负控因 `application/octet-stream` 失败，修复配置通过。浏览器仅覆盖该响应类型的诊断试验中，此前失败的 DOCX 的 11 页均渲染出非空文字与表格。最终发布还需移除浏览器覆盖，复核生产响应及同一 DOCX。
