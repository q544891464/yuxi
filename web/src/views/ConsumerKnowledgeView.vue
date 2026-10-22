<template>
  <main class="consumer-knowledge-view">
    <header class="page-heading">
      <div>
        <span class="eyebrow">知识资源</span>
        <h1>知识库</h1>
        <p>选择一个知识库，查看其中可访问的资料。</p>
      </div>
      <RouterLink
        v-if="isAdmin"
        class="manage-link"
        :to="{ path: '/extensions', query: { tab: 'knowledge' } }"
      >
        管理知识库
      </RouterLink>
    </header>

    <section class="knowledge-content" aria-label="可访问的知识库" :aria-busy="loading">
      <div v-if="loading" class="state-card" role="status">
        <LoaderCircle :size="20" class="state-icon spinning" />
        <span>正在加载知识库...</span>
      </div>
      <div v-else-if="error" class="state-card error-state" role="alert">
        <p>{{ error }}</p>
        <button type="button" class="retry-button" @click="loadDatabases">重试</button>
      </div>
      <div v-else-if="!databases.length" class="state-card empty-state">
        <Database :size="22" class="state-icon" />
        <strong>暂无可访问的知识库</strong>
        <span>有权限的知识库会显示在这里。</span>
      </div>
      <div v-else class="database-list">
        <button
          v-for="database in databases"
          :key="database.kb_id || database.id"
          type="button"
          class="database-card"
          @click="openDatabase(database)"
        >
          <span class="database-icon"><Database :size="19" /></span>
          <span class="database-copy">
            <strong>{{ database.name || '未命名知识库' }}</strong>
            <span>{{ database.description || '暂无描述' }}</span>
          </span>
          <ArrowRight :size="17" class="database-arrow" />
        </button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { ArrowRight, Database, LoaderCircle } from '@lucide/vue'
import { databaseApi } from '@/apis/knowledge_api'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)
const databases = ref([])
const loading = ref(false)
const error = ref('')

/** 加载后端按当前用户权限过滤的知识库列表。 */
async function loadDatabases() {
  loading.value = true
  error.value = ''
  try {
    const response = await databaseApi.getAccessibleDatabases()
    databases.value = Array.isArray(response?.databases) ? response.databases : []
  } catch {
    databases.value = []
    error.value = '知识库加载失败，请重试。'
  } finally {
    loading.value = false
  }
}

function openDatabase(database) {
  const kbId = database?.kb_id || database?.id
  if (!kbId) return
  router.push({ name: 'ConsumerKnowledgeBaseDetail', params: { kbId } })
}

onMounted(loadDatabases)
</script>

<style lang="less" scoped>
.consumer-knowledge-view {
  min-height: 100%;
  padding: clamp(24px, 5vw, 56px);
  background: var(--consumer-page-background);
  color: var(--consumer-brand-color);
}
.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  width: min(100%, 900px);
  margin: 0 auto 24px;
  h1 {
    margin: 5px 0 8px;
    color: var(--gray-1000);
    font-size: 28px;
    font-weight: 700;
  }
  p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 14px;
  }
}
.eyebrow {
  color: var(--consumer-muted-color);
  font-size: 12px;
}
.manage-link,
.retry-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--main-color);
  cursor: pointer;
  font-size: 13px;
  text-decoration: none;
  &:hover,
  &:focus-visible {
    border-color: var(--main-300);
    background: var(--main-10);
  }
  &:focus-visible {
    outline: 2px solid var(--main-300);
    outline-offset: 2px;
  }
}
.knowledge-content {
  width: min(100%, 900px);
  margin: 0 auto;
}
.database-list {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}
.database-card,
.state-card {
  border: 1px solid var(--gray-150);
  border-radius: 10px;
  background: var(--gray-0);
}
.database-card {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 82px;
  padding: 16px 18px;
  color: inherit;
  cursor: pointer;
  text-align: left;
  &:hover,
  &:focus-visible {
    border-color: var(--main-300);
    background: var(--main-10);
  }
  &:focus-visible {
    outline: 2px solid var(--main-300);
    outline-offset: 2px;
  }
}
.database-icon {
  display: grid;
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 10px;
  background: var(--main-30);
  color: var(--main-color);
}
.database-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  strong,
  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  strong {
    color: var(--gray-1000);
    font-size: 15px;
  }
  span {
    color: var(--color-text-secondary);
    font-size: 13px;
  }
}
.database-arrow {
  flex: 0 0 auto;
  color: var(--gray-500);
}
.state-card {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  color: var(--color-text-secondary);
  font-size: 13px;
  text-align: center;
  p {
    margin: 0;
  }
  strong {
    color: var(--gray-900);
  }
}
.state-icon {
  color: var(--main-color);
}
.error-state {
  color: var(--color-error-700);
}
.spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 640px) {
  .consumer-knowledge-view {
    padding: 24px 16px;
  }
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .database-card {
    padding: 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
