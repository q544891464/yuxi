import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { resolveConsumerChatReturnTarget } from '../../src/utils/consumerWorkspace.js'

const routerSource = readFileSync(new URL('../../src/router/index.js', import.meta.url), 'utf8')
const layoutSource = readFileSync(new URL('../../src/layouts/AppLayout.vue', import.meta.url), 'utf8')
const knowledgeSource = readFileSync(
  new URL('../../src/views/DataBaseInfoView.vue', import.meta.url),
  'utf8'
)
const uploadModalSource = readFileSync(
  new URL('../../src/components/FileUploadModal.vue', import.meta.url),
  'utf8'
)

test('消费端知识库与数据总览使用 chat 子路由并保留权限', () => {
  const chatRoute = routerSource.slice(routerSource.indexOf("path: '/chat'"), routerSource.indexOf("path: '/agent'"))

  assert.match(chatRoute, /path: 'knowledge\/:kbId'[\s\S]*name: 'ConsumerKnowledgeBaseDetail'/)
  assert.match(
    chatRoute,
    /path: 'dashboard'[\s\S]*name: 'ConsumerDashboard'[\s\S]*requiresAdmin: true/
  )
  assert.match(
    chatRoute,
    /name: 'ConsumerKnowledgeBaseDetail'[\s\S]*keepAlive: true[\s\S]*name: 'ConsumerDashboard'[\s\S]*keepAlive: true/
  )
  assert.ok(chatRoute.indexOf("path: 'knowledge/:kbId'") < chatRoute.indexOf("path: ':thread_id'"))
  assert.ok(chatRoute.indexOf("path: 'dashboard'") < chatRoute.indexOf("path: ':thread_id'"))
  assert.match(layoutSource, /name: 'ConsumerKnowledgeBaseDetail'/)
  assert.match(layoutSource, /name: 'ConsumerDashboard'/)
  assert.match(layoutSource, /const consumerBrandTarget = computed[\s\S]*ConsumerDashboard[\s\S]*resolveConsumerChatReturnTarget\(route\.query\.returnTo\)/)
  assert.match(layoutSource, /<RouterLink :to="consumerBrandTarget" class="consumer-brand">/)
  assert.match(layoutSource, /ConsumerKnowledgeBaseDetail'[\s\S]*query: \{ returnTo: route\.fullPath \}/)
  assert.match(layoutSource, /ConsumerDashboard'[\s\S]*query: \{ returnTo: route\.fullPath \}/)
  assert.doesNotMatch(layoutSource, /`\/extensions\/knowledgebase\/\$\{INSPECTION_KB_ID\}`/)
  assert.match(layoutSource, /:deep\(\.dashboard-container\)[\s\S]*height: 100%[\s\S]*overflow-y: auto/)
})

test('普通用户只读知识库不请求管理员文件类型配置', () => {
  assert.match(
    uploadModalSource,
    /const loadSupportedFileTypes = async \(\) => \{\s*if \(!userStore\.isAdmin\) \{[\s\S]*applySupportedFileTypes\(DEFAULT_SUPPORTED_TYPES\)[\s\S]*return/
  )
  assert.ok(
    uploadModalSource.indexOf('if (!userStore.isAdmin)') <
      uploadModalSource.indexOf('await fileApi.getSupportedFileTypes()')
  )
})

test('消费端知识库返回同一 chat 工作区', () => {
  assert.match(
    knowledgeSource,
    /if \(route\.meta\.consumerChat\)[\s\S]*resolveConsumerChatReturnTarget\(route\.query\.returnTo\)/
  )
  assert.equal(resolveConsumerChatReturnTarget('/chat/thread-1'), '/chat/thread-1')
  assert.equal(
    resolveConsumerChatReturnTarget('/chat?skill=skill-creator-v2'),
    '/chat?skill=skill-creator-v2'
  )
  assert.equal(resolveConsumerChatReturnTarget('/chat/thread-1?skill=review'), '/chat/thread-1?skill=review')
  assert.equal(resolveConsumerChatReturnTarget('/chat/knowledge/kb-1'), '/chat')
  assert.equal(resolveConsumerChatReturnTarget('https://example.com/chat'), '/chat')
})
