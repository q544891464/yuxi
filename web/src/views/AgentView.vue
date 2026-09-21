<template>
  <div class="agent-view" :class="{ 'consumer-agent': consumerChat }">
    <div class="agent-view-body">
      <!-- 中间内容区域 -->
      <div class="content">
        <AgentChatComponent
          ref="chatComponentRef"
          :single-mode="false"
          :initial-project-id="routeDraftProjectId"
          @thread-change="handleThreadChange"
          @skill-entry-cleared="handleSkillEntryCleared"
        >
          <template
            v-if="consumerChat"
            #welcome="{ skillEntry, skillAvailable, upload, projectName, uploadDisabled }"
          >
            <ChatWelcome :skill-selected="!!skillEntry" :ducha="!!route.meta.ducha">
              <template #skill-description>
                <SkillStartPanel
                  :entry="skillEntry"
                  :available="skillAvailable"
                  :disabled="uploadDisabled"
                  :project-name="projectName"
                  @upload="upload"
                />
              </template>
            </ChatWelcome>
          </template>
          <template v-if="consumerChat" #input-decoration="{ isStartScreen }">
            <div v-if="!isStartScreen" class="composer-mascot" aria-hidden="true">
              <img src="/cydx/assistant-cutout.png" alt="" draggable="false" />
            </div>
          </template>
          <template #input-actions-left="{ hasActiveThread, isCreatingThread }">
            <a-dropdown
              v-if="selectedAgentId"
              v-model:open="agentDropdownOpen"
              :trigger="['click']"
              placement="topLeft"
              overlay-class-name="config-dropdown-overlay"
            >
              <button
                ref="agentDropdownTriggerRef"
                type="button"
                class="input-action-btn config-dropdown-trigger"
                :class="{ disabled: isLoadingConfig || isCreatingThread }"
                :disabled="isCreatingThread"
                :aria-label="currentAgentLabel"
              >
                <FallbackAvatar
                  v-if="currentAgentOption"
                  class="config-dropdown-compact-icon"
                  :src="currentAgentOption.icon"
                  :default-src="currentAgentOption.defaultIcon"
                  :name="currentAgentOption.label"
                  :seed="currentAgentOption.value || currentAgentOption.label"
                  kind="agent"
                  :size="20"
                  shape="rounded"
                  alt=""
                />
                <span class="hide-text config-dropdown-text">{{ currentAgentLabel }}</span>
                <ChevronDown size="15" class="config-dropdown-chevron" />
              </button>

              <template #overlay>
                <div ref="agentDropdownPanelRef" class="config-dropdown-panel">
                  <button
                    v-for="agent in agentQuickSwitchOptions"
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
                    <span class="config-dropdown-item-label">{{ agent.label }}</span>
                    <span v-if="agent.isBuiltin" class="config-dropdown-item-badge">内置</span>
                    <Check
                      v-if="agent.value === selectedAgentId"
                      :size="14"
                      class="config-dropdown-item-check"
                    />
                  </button>

                  <div v-if="hasActiveThread" class="config-dropdown-hint">
                    当前对话已绑定智能体，新对话可切换。
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
                </div>
              </template>
            </a-dropdown>
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
import { Settings2, ChevronDown, Check, Plus } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import { agentApi } from '@/apis/agent_api'
import { useOutsidePointerdown } from '@/composables/useOutsidePointerdown'
import ChatWelcome from '@/components/ChatWelcome.vue'
import SkillStartPanel from '@/components/SkillStartPanel.vue'
import AgentChatComponent from '@/components/AgentChatComponent.vue'
import AgentEditModal from '@/components/model-management/AgentEditModal.vue'
import { isBuiltinAgent, useAgentStore } from '@/stores/agent'
import { handleChatError } from '@/utils/errorHandler'
import { generatePixelAvatar } from '@/utils/pixelAvatar'
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
const entryRoute = computed(() =>
  route.meta.ducha ? 'DuchaChatComp' : consumerChat.value ? 'ChatComp' : 'AgentComp'
)

// 从 agentStore 中获取响应式状态
const { agents, selectedAgentId, isLoadingConfig } = storeToRefs(agentStore)

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
  const requestedSkill = route.query.skill
  syncingRouteThread.value = true
  try {
    if (!threadId && !agentStore.isInitialized) {
      await agentStore.initialize()
    }

    if (version !== routeSyncVersion || !agentStore.isInitialized) return

    const ok = await chatComponent.selectThreadFromRoute(threadId)
    if (ok === null || version !== routeSyncVersion) return
    if (!threadId && requestedSkill) {
      const selection = await chatComponent.prepareSkillEntry(String(requestedSkill))
      if (selection?.accepted === false && version === routeSyncVersion) {
        await router.replace({
          name: entryRoute.value,
          query: { ...route.query, skill: selection.activeId || undefined }
        })
      }
    } else if (!threadId) {
      chatComponent.clearSkillEntry()
    }
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
  () => [
    route.params.thread_id,
    route.query.skill,
    route.query.project_id,
    agentStore.isInitialized
  ],
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

const handleSkillEntryCleared = () => {
  if (getRouteThreadId() || !route.query.skill) return
  router.replace({ name: entryRoute.value, query: { ...route.query, skill: undefined } })
}

const agentQuickSwitchOptions = computed(() =>
  (agents.value || [])
    .filter((agent) => !agent.is_subagent)
    .map((agent) => ({
      label: agent.name || agent.id,
      value: agent.id,
      icon: agent.icon || '',
      defaultIcon: agent.id ? generatePixelAvatar(agent.id) : '',
      isBuiltin: isBuiltinAgent(agent)
    }))
)

const currentAgentOption = computed(() =>
  agentQuickSwitchOptions.value.find((agent) => agent.value === selectedAgentId.value)
)

const currentAgentLabel = computed(() => {
  if (isLoadingConfig.value) return '加载中...'
  return currentAgentOption.value?.label || '智能体'
})

const agentDropdownOpen = ref(false)
const agentDropdownTriggerRef = ref(null)
const agentDropdownPanelRef = ref(null)
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

useOutsidePointerdown(agentDropdownOpen, [agentDropdownTriggerRef, agentDropdownPanelRef])
</script>

<style lang="less" scoped>
.agent-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
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

.config-dropdown-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  max-width: min(240px, calc(100vw - 160px));
  gap: 4px;
}

.config-dropdown-trigger :deep(svg) {
  color: currentColor;
}

.config-dropdown-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: currentColor;
}

.config-dropdown-chevron {
  flex-shrink: 0;
  color: currentColor;
}

.config-dropdown-compact-icon {
  display: none;
  flex-shrink: 0;
}

@container (max-width: 640px) {
  .config-dropdown-trigger {
    width: 30px;
    padding-inline: 0;
  }

  .config-dropdown-compact-icon {
    display: block;
  }

  .config-dropdown-text,
  .config-dropdown-chevron {
    display: none;
  }
}

// 响应式优化
@media (max-width: 520px) {
  .config-dropdown-trigger {
    max-width: calc(100vw - 112px);
  }
}
.composer-mascot {
  position: absolute;
  left: 18px;
  bottom: 100%;
  width: 150px;
  height: 157px;
  pointer-events: none;
  z-index: 20;
  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: left bottom;
    pointer-events: none;
  }
}
</style>
