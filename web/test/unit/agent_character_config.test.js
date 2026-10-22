import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(
  new URL('../../src/components/model-management/AgentEditModal.vue', import.meta.url),
  'utf8'
)

test('人物形象配置说明用途、格式并提供完整图片预览', () => {
  assert.match(source, /<span id="agent-character-title" class="agent-character-title">人物形象<\/span>/)
  assert.match(source, /显示在欢迎页和对话框旁/)
  assert.match(source, /透明背景的 PNG 或 WebP/)
  assert.match(source, /aria-label="人物形象完整预览"[\s\S]*?object-fit:\s*contain;/)
  assert.match(source, /getDefaultEmployeePortrait\(\{ slug: agentForm\.slug \|\| editingAgentId\.value \}\)/)
  assert.match(source, /:src="agentForm\.icon \|\| agentPreviewDefaultIcon"/)
})

test('默认人物形象可选但不会绕过表单保存，上传期间选项禁用', () => {
  assert.match(source, /v-for="portrait in DEFAULT_EMPLOYEE_PORTRAITS"/)
  assert.match(source, /@click="agentForm\.icon = portrait\.src"/)
  assert.match(source, /:disabled="agentIconUploading"\s*@click="agentForm\.icon = portrait\.src"/)
  assert.match(source, /icon: agentForm\.icon\.trim\(\) \|\| null/)
})

test('人物形象上传入口可见且保留上传校验与保存等待', () => {
  assert.match(source, /:before-upload="beforeAgentIconUpload"/)
  assert.match(source, /上传人物形象/)
  assert.match(source, /更换人物形象/)
  assert.match(source, /file\.type\.startsWith\('image\/'\)/)
  assert.match(source, /file\.size > MAX_IMAGE_UPLOAD_SIZE_BYTES/)
  assert.match(source, /if \(agentIconUploading\.value\)\s*{\s*const pendingUpload = agentIconUploadPromise\s*if \(!pendingUpload \|\| !\(await pendingUpload\)\) return/s)
})
