<template>
  <a-result
    status="warning"
    title="暂时无法读取页面权限"
    sub-title="请检查网络后重试。权限确认前不会进入工作区。"
  >
    <template #extra><a-button type="primary" @click="retry">重新加载</a-button></template>
  </a-result>
</template>
<script setup>
import { useRoute, useRouter } from 'vue-router'
import { sanitizeRedirect } from '@/utils/oidcAutoStart'
const route = useRoute()
const router = useRouter()
const retry = () => router.replace(sanitizeRedirect(route.query.redirect))
</script>
