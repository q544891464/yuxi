<template>
  <main class="employee-square">
    <header class="square-header">
      <div>
        <p class="eyebrow">Yuxi</p>
        <h1>选择数字员工</h1>
        <p class="square-description">选择一个员工开始新的对话。已有对话会继续由原员工处理。</p>
      </div>
      <a-button v-if="userStore.isAdmin" @click="goToManagement">
        <template #icon><Settings2 :size="16" /></template>
        配置数字员工
      </a-button>
    </header>

    <p class="access-note">
      系统助手对所有用户开放；自建员工由管理员设置共享范围后显示在这里。
    </p>

    <label class="employee-search">
      <Search :size="18" aria-hidden="true" />
      <span class="sr-only">搜索数字员工</span>
      <input v-model="keyword" type="search" placeholder="搜索名称或用途" />
    </label>

    <div v-if="loading" class="square-state" role="status" aria-live="polite">
      <a-spin />
      <span>正在加载可用员工…</span>
    </div>
    <a-result v-else-if="error" status="error" title="员工列表加载失败" :sub-title="error">
      <template #extra><a-button type="primary" @click="load">重试</a-button></template>
    </a-result>
    <section v-else-if="!employees.length" class="square-state" role="status">
      <UsersRound :size="24" aria-hidden="true" />
      <strong>{{ keyword.trim() ? '没有匹配的数字员工' : '暂时没有可用的数字员工' }}</strong>
      <span>{{ keyword.trim() ? '试试其他名称或用途。' : '请联系管理员配置并共享员工。' }}</span>
      <a-button v-if="userStore.isAdmin && !keyword.trim()" @click="goToManagement">
        配置数字员工
      </a-button>
    </section>
    <section v-else class="employee-grid" aria-label="可用数字员工">
      <article v-for="agent in employees" :key="agent.slug || agent.id" class="employee-card">
        <FallbackAvatar
          class="employee-avatar"
          :src="agent.icon || ''"
          :default-src="defaultAvatar(agent)"
          :name="agent.name || '数字员工'"
          :seed="agent.slug || agent.id"
          kind="agent"
          :size="56"
          shape="rounded"
        />
        <h2 :title="agent.name || '未命名员工'">{{ agent.name || '未命名员工' }}</h2>
        <p class="employee-description" :title="agent.description || ''">
          {{ agent.description || '可以开始新的对话。' }}
        </p>
        <div class="employee-actions">
          <a-button
            type="primary"
            :loading="openingId === keyFor(agent)"
            :disabled="!!openingId && openingId !== keyFor(agent)"
            @click="startChat(agent)"
          >
            开始对话
          </a-button>
          <a-button
            v-if="isDefault(agent)"
            :loading="defaultPendingId === keyFor(agent)"
            :disabled="!!defaultPendingId"
            @click="clearDefault"
          >
            取消默认
          </a-button>
          <a-button
            v-else
            :loading="defaultPendingId === keyFor(agent)"
            :disabled="!!defaultPendingId"
            @click="setDefault(agent)"
          >
            设为默认
          </a-button>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { Search, Settings2, UsersRound } from '@lucide/vue'
import { agentApi } from '@/apis/agent_api'
import { userConfigApi } from '@/apis/user_config_api'
import { useUserStore } from '@/stores/user'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'
import { normalizeAgent } from '@/utils/agentConfigUtils'
import { generatePixelAvatar } from '@/utils/pixelAvatar'
import { resolveDefaultEmployee, searchEmployees } from '@/utils/digitalEmployees'

const router = useRouter()
const userStore = useUserStore()
const agents = ref([])
const defaultAgentId = ref(null)
const keyword = ref('')
const loading = ref(true)
const error = ref('')
const defaultPendingId = ref('')
const openingId = ref('')

const employees = computed(() => searchEmployees(agents.value, keyword.value))

/** 重新读取可见员工和服务端保存的个人默认值。 */
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [agentResponse, config] = await Promise.all([agentApi.getAgents(), userConfigApi.get()])
    agents.value = (agentResponse.agents || []).map(normalizeAgent).filter((agent) => !agent.is_subagent)
    defaultAgentId.value = resolveDefaultEmployee(config.default_agent_id, agents.value)?.slug || null
  } catch (err) {
    error.value = err?.message || '请检查连接后重试。'
  } finally {
    loading.value = false
  }
}

/** 以员工标识生成稳定操作键。 */
const keyFor = (agent) => agent.slug || agent.id

/** 判断员工是否为服务端保存的默认入口。 */
const isDefault = (agent) => defaultAgentId.value === keyFor(agent)

/** 打开独立新对话，避免把已有会话绑定到另一员工。 */
const startChat = async (agent) => {
  const id = keyFor(agent)
  if (!id || openingId.value) return
  openingId.value = id
  try {
    await router.push({ path: '/chat', query: { agent_id: id } })
  } finally {
    openingId.value = ''
  }
}

/** 保存当前可见员工作为跨设备默认入口。 */
const setDefault = async (agent) => {
  const id = keyFor(agent)
  if (!id || defaultPendingId.value) return
  defaultPendingId.value = id
  try {
    const config = await userConfigApi.update({ default_agent_id: id })
    defaultAgentId.value = config.default_agent_id ?? id
    message.success('已设为默认数字员工')
  } catch (err) {
    message.error(err?.message || '设置默认员工失败，请重试')
  } finally {
    defaultPendingId.value = ''
  }
}

/** 清除个人默认值，使根路径返回员工广场。 */
const clearDefault = async () => {
  if (!defaultAgentId.value || defaultPendingId.value) return
  defaultPendingId.value = defaultAgentId.value
  try {
    await userConfigApi.update({ default_agent_id: null })
    defaultAgentId.value = null
    message.success('已取消默认数字员工')
  } catch (err) {
    message.error(err?.message || '取消默认员工失败，请重试')
  } finally {
    defaultPendingId.value = ''
  }
}

const defaultAvatar = (agent) => generatePixelAvatar(keyFor(agent))

const goToManagement = () => router.push('/agent-manage')

onMounted(load)
</script>

<style lang="less" scoped>
.employee-square {
  width: min(1120px, 100%);
  min-height: 100%;
  margin: 0 auto;
  padding: 32px 28px 48px;
  color: var(--color-text);
  overflow-y: auto;
}

.square-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;

  h1 {
    margin: 2px 0 8px;
    color: var(--color-text);
    font-size: 24px;
    font-weight: 600;
  }
}

.eyebrow {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.square-description,
.access-note {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.access-note {
  margin-top: 20px;
  padding: 10px 12px;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  background: var(--gray-10);
  font-size: 13px;
}

.employee-search {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(420px, 100%);
  height: 42px;
  margin: 24px 0;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  background: var(--gray-0);
  color: var(--color-text-secondary);

  &:focus-within {
    border-color: var(--main-color);
    outline: 2px solid var(--main-30);
  }

  input {
    width: 100%;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--color-text);
    font: inherit;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.employee-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
  gap: 16px;
}

.employee-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  padding: 20px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);

  h2 {
    max-width: 100%;
    margin: 16px 0 6px;
    overflow: hidden;
    color: var(--color-text);
    font-size: 17px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.employee-description {
  display: -webkit-box;
  min-height: 44px;
  margin: 0 0 20px;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.employee-actions {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}

.square-state {
  display: flex;
  min-height: 240px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-secondary);
  text-align: center;

  strong {
    color: var(--color-text);
  }
}

@media (max-width: 767px) {
  .employee-square {
    padding: 24px 16px 32px;
  }

  .square-header {
    flex-direction: column;
    align-items: stretch;

    h1 {
      font-size: 21px;
    }
  }

  .square-header :deep(.ant-btn) {
    align-self: flex-start;
  }
}
</style>
