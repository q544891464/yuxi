<script setup>
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
</script>
<template>
  <a-config-provider :theme="themeStore.currentTheme" :locale="zhCN">
    <router-view v-slot="{ Component }">
      <component :is="Component" v-if="Component" />
      <div v-else class="entry-loading" role="status">
        <a-spin />
        <p>正在加载，请稍候…</p>
      </div>
    </router-view>
  </a-config-provider>
</template>

<style scoped>
.entry-loading {
  min-height: 100vh;
  display: grid;
  place-content: center;
  text-align: center;
  gap: 16px;
  color: var(--gray-600);
  background: var(--consumer-page-background);
}
</style>
