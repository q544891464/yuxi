<template>
  <div class="extensions-view extension-page-root">
    <PageHeader
      v-if="!isDetailPage"
      v-model:active-key="activeTab"
      title="技能管理"
      :tabs="extensionTabs"
      :loading="activeChildLoading"
      :show-border="true"
      aria-label="技能管理视图切换"
    />

    <div v-if="!isDetailPage" class="extensions-content">
      <div v-if="userStore.isAdmin && activeTab === 'tools'" class="tab-panel">
        <ToolsCardList ref="toolsRef" />
      </div>
      <div v-if="activeTab === 'skills'" class="tab-panel">
        <SkillCardList ref="skillsRef" />
      </div>
      <div v-if="userStore.isAdmin && activeTab === 'mcp'" class="tab-panel">
        <McpCardList ref="mcpRef" />
      </div>
      <div
        v-if="userStore.isAdmin && activeTab === 'navigation'"
        class="tab-panel navigation-panel"
      >
        <SkillNavigationSettings />
      </div>
    </div>

    <router-view v-else :key="route.path" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ToolsCardList from '@/components/extensions/ToolsCardList.vue'
import McpCardList from '@/components/extensions/McpCardList.vue'
import SkillCardList from '@/components/extensions/SkillCardList.vue'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkillNavigationSettings from '@/components/SkillNavigationSettings.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const activeTab = ref(null)
const skillsRef = ref(null)
const mcpRef = ref(null)
const toolsRef = ref(null)

const adminExtensionTabs = computed(() => [
  { key: 'skills', label: '技能' },
  { key: 'tools', label: '工具' },
  { key: 'mcp', label: 'MCP' },
  { key: 'navigation', label: '侧栏技能' }
])
const userExtensionTabs = [{ key: 'skills', label: '技能' }]
const extensionTabs = computed(() =>
  userStore.isAdmin ? adminExtensionTabs.value : userExtensionTabs
)
const allowedTabKeys = computed(() => extensionTabs.value.map((tab) => tab.key))
const defaultTabKey = computed(() => extensionTabs.value[0]?.key || 'skills')

const normalizeTab = (tab) => {
  if (allowedTabKeys.value.includes(tab)) return tab
  return defaultTabKey.value
}

const replaceTabQuery = (tab) => {
  const query = { ...route.query }
  if (tab === defaultTabKey.value) {
    delete query.tab
  } else {
    query.tab = tab
  }
  router.replace({ query })
}

const isDetailPage = computed(() => {
  return route.path.startsWith('/extensions/mcp/') || route.path.startsWith('/extensions/skill/')
})

const activeChildLoading = computed(() => {
  const refMap = {
    tools: toolsRef,
    skills: skillsRef,
    mcp: mcpRef
  }
  const child = refMap[activeTab.value]
  return child?.value?.loading || false
})

watch(
  () => [route.query.tab, userStore.isAdmin],
  ([tab]) => {
    const nextTab = normalizeTab(tab)
    if (activeTab.value !== nextTab) activeTab.value = nextTab
    if (tab && tab !== nextTab) replaceTabQuery(nextTab)
  },
  { immediate: true }
)

watch(activeTab, (tab) => {
  if (!tab) return
  const nextTab = normalizeTab(tab)
  if (nextTab !== tab) {
    activeTab.value = nextTab
    return
  }
  if (route.query.tab === nextTab || (!route.query.tab && nextTab === defaultTabKey.value)) return
  replaceTabQuery(nextTab)
})
</script>

<style scoped lang="less">
@import '@/assets/css/extensions.less';

.extensions-view {
  @media (max-width: 600px) {
    :deep(.page-header) {
      height: auto;
      padding-top: 12px;
      padding-bottom: 12px;
    }

    :deep(.page-header-left) {
      flex-direction: column;
      align-items: flex-start;
    }

    :deep(.page-header-tabs) {
      border-left: 0;
      padding-left: 0;
      margin-left: 0;
      height: auto;
    }
  }

  .extensions-content {
    flex: 1;
    min-height: 0;
    overflow: hidden;

    .tab-panel {
      height: 100%;
      min-height: 0;
      overflow-y: auto;
    }

    .navigation-panel {
      padding: 24px;
    }
  }
}
</style>
