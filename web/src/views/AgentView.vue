<template>
  <div class="agent-view" :class="{ 'consumer-agent': consumerChat }">
    <div class="agent-view-body">
      <!-- 中间内容区域 -->
      <div class="content">
        <AgentChatComponent
          ref="chatComponentRef"
          :single-mode="false"
          :initial-project-id="routeDraftProjectId"
          :is-new-conversation="!getRouteThreadId()"
          @thread-change="handleThreadChange"
        >
          <template v-if="consumerChat" #welcome="{ openUpload }">
            <ChatWelcome :agent="selectedAgent">
              <template v-if="selectedSkill" #skill-description>
                <section class="skill-start-panel" aria-label="技能说明">
                  <h3>
                    {{ selectedSkill.display_name || selectedSkill.name || selectedSkill.slug }}
                  </h3>
                  <p>
                    {{ selectedSkill.description || '请上传所需材料，或在输入框中描述您的需求。' }}
                  </p>
                  <p v-if="selectedNavigationEntry?.material">
                    <strong>准备材料：</strong>{{ selectedNavigationEntry.material }}
                  </p>
                  <p v-if="selectedNavigationEntry?.result">
                    <strong>用途与结果：</strong>{{ selectedNavigationEntry.result }}
                  </p>
                  <a-button type="primary" @click="openUpload">上传材料</a-button>
                  <span>已引用该技能，编辑需求后点击发送开始使用。</span>
                </section>
              </template>
            </ChatWelcome>
          </template>
          <template v-if="consumerChat" #input-decoration="{ isStartScreen }">
            <div v-if="!isStartScreen" class="composer-mascot" aria-hidden="true">
              <EmployeePortrait :agent="selectedAgent" />
            </div>
          </template>
          <template #input-actions-left="{ hasActiveThread, isCreatingThread }">
            <ActionDropdown
              upward
              v-if="selectedAgentId"
              v-model:open="agentDropdownOpen"
              v-model:search="agentSearchKeyword"
              search-placeholder="搜索数字员工"
              :disabled="isCreatingThread"
            >
              <template #trigger>
                <ActionTrigger
                  :label="currentAgentLabel"
                  :open="agentDropdownOpen"
                  :disabled="isCreatingThread"
                  collapse-label
                >
                  <template #icon>
                    <FallbackAvatar
                      v-if="currentAgentOption"
                      :src="currentAgentOption.icon"
                      :default-src="currentAgentOption.defaultIcon"
                      :name="currentAgentOption.label"
                      :seed="currentAgentOption.value || currentAgentOption.label"
                      kind="agent"
                      :size="20"
                      shape="rounded"
                      alt=""
                    />
                  </template>
                </ActionTrigger>
              </template>
              <div v-if="!filteredAgentOptions.length" class="agent-switch-empty" role="status">
                暂无匹配数字员工
              </div>
              <button
                v-for="agent in filteredAgentOptions"
                :key="agent.value"
                type="button"
                class="config-dropdown-item"
                :class="{
                  selected: agent.value === selectedAgentId,
                  disabled: hasActiveThread && agent.value !== selectedAgentId
                }"
                @click="handleAgentSwitch(agent.value, hasActiveThread, isCreatingThread)"
              >
                <FallbackAvatar
                  class="config-dropdown-item-icon-image"
                  :src="agent.icon"
                  :default-src="agent.defaultIcon"
                  :name="agent.label"
                  :seed="agent.value || agent.label"
                  kind="agent"
                  :size="24"
                  shape="rounded"
                  :alt="`${agent.label}图标`"
                />
                <span class="config-dropdown-item-label" :title="agent.label">{{
                  agent.label
                }}</span>
                <span v-if="agent.isBuiltin" class="config-dropdown-item-badge">内置</span>
                <Check
                  v-if="agent.value === selectedAgentId"
                  :size="14"
                  class="config-dropdown-item-check"
                />
              </button>
              <template #footer>
                <div v-if="hasActiveThread" class="config-dropdown-hint">
                  当前对话已绑定数字员工，新对话可切换。
                </div>

                <div class="config-dropdown-divider"></div>

                <div v-if="!consumerChat" class="config-dropdown-actions">
                  <button
                    type="button"
                    class="config-dropdown-item action-item"
                    @click="openAgentManagement"
                  >
                    <Settings2 :size="15" class="config-dropdown-item-icon" />
                    <span class="config-dropdown-item-label">编辑智能体</span>
                  </button>
                  <button
                    type="button"
                    class="config-dropdown-item action-item"
                    @click="openCreateAgent"
                  >
                    <Plus :size="15" class="config-dropdown-item-icon" />
                    <span class="config-dropdown-item-label">新建智能体</span>
                  </button>
                </div>
              </template>
            </ActionDropdown>
          </template>
        </AgentChatComponent>
      </div>
    </div>
    <AgentEditModal
      v-if="!consumerChat"
      ref="agentEditModalRef"
      :backend-options="agentBackendOptions"
      @saved="handleAgentSaved"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { Settings2, Check, Plus } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import { agentApi } from '@/apis/agent_api'
import ChatWelcome from '@/components/ChatWelcome.vue'
import EmployeePortrait from '@/components/EmployeePortrait.vue'
import { listAccessibleSkills } from '@/apis/skill_api'
import { normalizeAccessibleSkills, findNavigationEntry } from '@/utils/accessibleSkills'
import { useSkillNavigationStore } from '@/stores/skillNavigation'
import { CREATE_SKILL_INTENT, CREATOR_SKILL_SLUG } from '@/utils/skillDraft'
import ActionDropdown from '@/components/common/ActionDropdown.vue'
import ActionTrigger from '@/components/common/ActionTrigger.vue'
import AgentChatComponent from '@/components/AgentChatComponent.vue'
import AgentEditModal from '@/components/model-management/AgentEditModal.vue'
import { isBuiltinAgent, useAgentStore } from '@/stores/agent'
import { handleChatError } from '@/utils/errorHandler'
import { getDefaultEmployeePortrait } from '@/utils/employeePortraits'
import { normalizeAgentBackendOption } from '@/utils/agentConfigUtils'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'

import { storeToRefs } from 'pinia'

// 组件引用
const chatComponentRef = ref(null)
const agentEditModalRef = ref(null)

// Stores
const agentStore = useAgentStore()
const route = useRoute()
const router = useRouter()
const consumerChat = computed(() => route.meta.consumerChat === true)
const entryRoute = computed(() => (consumerChat.value ? 'ChatComp' : 'AgentComp'))

const selectedSkill = ref(null)
const selectedNavigationEntry = ref(null)
const skillNavigation = useSkillNavigationStore()
let skillSelectionVersion = 0
/** 仅将可访问列表中的技能带入当前新会话草稿。 */
const consumeRouteSkill = async () => {
  const intent = route.query.skill
  const slug = intent === CREATE_SKILL_INTENT ? CREATOR_SKILL_SLUG : intent
  const version = ++skillSelectionVersion
  selectedSkill.value = null
  selectedNavigationEntry.value = null
  if (
    typeof slug !== 'string' ||
    !slug ||
    getRouteThreadId() ||
    !chatComponentRef.value ||
    !agentStore.isInitialized
  )
    return
  try {
    await syncSelectedThreadFromRoute()
    await skillNavigation.load()
    const entryId = route.query.skill_entry
    const entry = entryId ? findNavigationEntry(skillNavigation.tree, entryId, slug) : null
    if (entryId && !entry) {
      message.warning('该技能入口已移除或您暂无查看权限，请重新选择')
      return
    }
    const skills = normalizeAccessibleSkills(await listAccessibleSkills())
    if (version !== skillSelectionVersion || route.query.skill !== intent || getRouteThreadId())
      return
    const skill = skills.find((item) => item.slug === slug)
    if (!skill) {
      message.warning('该技能不可用或您暂无访问权限')
      return
    }
    if (chatComponentRef.value?.applySkillToDraft(skill, entry?.prompt)) {
      selectedSkill.value = entry ? { ...skill, display_name: entry.name } : skill
      selectedNavigationEntry.value = entry
    } else message.warning('当前数字员工未启用此技能，请切换数字员工或联系管理员配置')
  } catch (error) {
    message.error(error?.message || '技能加载失败，请重新选择')
  }
}
watch(
  () => [
    route.query.skill,
    route.query.skill_entry,
    skillNavigation.tree,
    route.params.thread_id,
    route.query.project_id,
    agentStore.selectedAgentId,
    agentStore.isInitialized,
    chatComponentRef.value
  ],
  consumeRouteSkill,
  { flush: 'post' }
)

// 从 agentStore 中获取响应式状态
const { agents, selectedAgent, selectedAgentId, isLoadingConfig } = storeToRefs(agentStore)

const syncingRouteThread = ref(false)
let routeSyncVersion = 0

const getRouteThreadId = () => {
  const value = route.params.thread_id
  return typeof value === 'string' ? value : ''
}

const getRouteAgentId = () => {
  const value = route.query.agent_id
  return typeof value === 'string' ? value : ''
}

const routeDraftProjectId = computed(() => {
  if (getRouteThreadId()) return ''
  const value = route.query.project_id
  return typeof value === 'string' ? value : ''
})

const syncSelectedThreadFromRoute = async () => {
  const chatComponent = chatComponentRef.value
  if (!chatComponent?.selectThreadFromRoute) return

  const threadId = getRouteThreadId()
  const version = ++routeSyncVersion
  syncingRouteThread.value = true
  try {
    if (!threadId && !agentStore.isInitialized) {
      await agentStore.initialize()
    }

    if (version !== routeSyncVersion || !agentStore.isInitialized) return

    const ok = await chatComponent.selectThreadFromRoute(threadId)
    if (ok === null || version !== routeSyncVersion) return
    if (threadId && !ok) {
      await router.replace({ name: entryRoute.value })
    }
  } catch (error) {
    handleChatError(error, 'load')
  } finally {
    if (version === routeSyncVersion) syncingRouteThread.value = false
  }
}

const consumeRouteAgentSelection = async () => {
  const targetAgentId = getRouteAgentId()
  if (!targetAgentId || getRouteThreadId()) return

  try {
    if (!agentStore.isInitialized) {
      await agentStore.initialize()
    }

    await nextTick()
    const canSwitch = await chatComponentRef.value?.selectThreadFromRoute?.('')
    if (canSwitch === null) return
    await agentStore.selectAgent(targetAgentId)
  } catch (error) {
    handleChatError(error, 'load')
  } finally {
    const nextQuery = { ...route.query }
    delete nextQuery.agent_id
    await router.replace({ name: entryRoute.value, query: nextQuery })
  }
}

watch(
  () => [route.params.thread_id, route.query.project_id, agentStore.isInitialized],
  () => {
    syncSelectedThreadFromRoute()
  },
  { immediate: true }
)

watch(
  () => route.query.agent_id,
  () => {
    consumeRouteAgentSelection()
  },
  { immediate: true }
)

watch(chatComponentRef, (instance) => {
  if (!instance) return
  syncSelectedThreadFromRoute()
})

const handleThreadChange = (threadId) => {
  if (syncingRouteThread.value) return
  const currentRouteThreadId = getRouteThreadId()
  const nextThreadId = threadId || ''
  if (currentRouteThreadId === nextThreadId) return

  if (nextThreadId) {
    router.replace({ name: `${entryRoute.value}WithThreadId`, params: { thread_id: nextThreadId } })
  } else {
    router.replace({ name: entryRoute.value })
  }
}

const agentQuickSwitchOptions = computed(() =>
  (agents.value || [])
    .filter((agent) => !agent.is_subagent)
    .map((agent) => ({
      label: agent.name || agent.id,
      value: agent.id,
      icon: agent.icon || '',
      defaultIcon: getDefaultEmployeePortrait(agent),
      isBuiltin: isBuiltinAgent(agent)
    }))
)

const currentAgentOption = computed(() =>
  agentQuickSwitchOptions.value.find((agent) => agent.value === selectedAgentId.value)
)

const currentAgentLabel = computed(() => {
  if (isLoadingConfig.value) return '加载中...'
  return currentAgentOption.value?.label || '数字员工'
})

const agentSearchKeyword = ref('')
const filteredAgentOptions = computed(() => {
  const keyword = agentSearchKeyword.value.trim().toLocaleLowerCase()
  return agentQuickSwitchOptions.value.filter((agent) =>
    agent.label.toLocaleLowerCase().includes(keyword)
  )
})

const agentDropdownOpen = ref(false)
const agentBackendOptions = ref([])
const agentBackendsLoaded = ref(false)

const loadAgentBackends = async () => {
  if (agentBackendsLoaded.value) return
  const response = await agentApi.getAgentBackends()
  agentBackendOptions.value = (response.backends || []).map(normalizeAgentBackendOption)
  agentBackendsLoaded.value = true
}

const handleAgentSwitch = async (agentId, hasActiveThread, isCreatingThread) => {
  if (!agentId || agentId === selectedAgentId.value) return
  if (isCreatingThread) {
    message.info('正在创建新对话，请稍候')
    return
  }
  if (hasActiveThread) {
    message.info('当前对话已绑定智能体，请新建对话后切换')
    return
  }
  try {
    await agentStore.selectAgent(agentId)
    agentDropdownOpen.value = false
  } catch (error) {
    console.error('切换智能体出错:', error)
    message.error('切换智能体失败')
  }
}

const handleAgentSaved = async ({ mode, agent } = {}) => {
  if (mode === 'create' && !agent?.is_subagent) {
    await chatComponentRef.value?.selectThreadFromRoute?.('')
  }

  await agentStore.fetchAgents()
  if (selectedAgentId.value) {
    await agentStore.fetchAgentDetail(selectedAgentId.value, true)
  }
}

const openCreateAgent = async () => {
  agentDropdownOpen.value = false
  try {
    await loadAgentBackends()
    agentEditModalRef.value?.openCreate()
  } catch (error) {
    message.error(error.message || '打开新建智能体弹窗失败')
  }
}

const openAgentManagement = async () => {
  agentDropdownOpen.value = false
  if (!selectedAgentId.value) {
    message.warning('请先选择智能体')
    return
  }
  try {
    await loadAgentBackends()
    await agentEditModalRef.value?.openEdit(selectedAgentId.value)
  } catch (error) {
    message.error(error.message || '打开智能体配置失败')
  }
}
</script>

<style lang="less" scoped>
.composer-mascot {
  position: absolute;
  left: 18px;
  bottom: calc(100% - 16px);
  width: 150px;
  height: 150px;
  pointer-events: none;
  z-index: 2;
}
.skill-start-panel {
  margin-top: 12px;
  padding: 16px 20px;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 18px;
}
.skill-start-panel h3 {
  margin: 0 0 8px;
  color: var(--main-600);
  font-size: 16px;
}
.skill-start-panel p {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.skill-start-panel span {
  margin-left: 12px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.agent-switch-empty {
  padding: 20px 8px;
  color: var(--gray-500);
  text-align: center;
  font-size: 13px;
}

.agent-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.agent-view-body {
  --gap-radius: 6px;
  display: flex;
  flex-direction: row;
  width: 100%;
  flex: 1;
  height: 100%;
  overflow: hidden;
  position: relative;

  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
}

.content {
  flex: 1;
  overflow: hidden;
}
</style>
