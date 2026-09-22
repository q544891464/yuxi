<template>
  <section>
    <h2>角色页面权限</h2>
    <p>设置角色可进入的页面与登录首页。配置不增加知识库、技能或文件的数据权限。</p>
    <p>超级管理员保留全部管理入口；督查工作区包含其对话详情。</p>
    <a-alert v-if="error" type="error" :message="error" show-icon />
    <a-button :loading="loading" :disabled="saving" @click="load">重新加载</a-button>
    <div v-if="config" class="role-rules">
      <section v-for="(label, role) in roles" :key="role" class="role-rule">
        <h3>{{ label }}</h3>
        <a-switch
          :checked="config.rules[role].pages !== null"
          :disabled="saving"
          @change="setRestricted(role, $event)"
        />
        <span> 限制可访问页面</span>
        <div v-if="config.rules[role].pages !== null">
          <label>允许访问</label>
          <a-select
            mode="multiple"
            :value="config.rules[role].pages"
            :options="options(role)"
            :disabled="saving"
            style="width: 100%"
            :aria-label="`${label}允许页面`"
            @change="setPages(role, $event)"
          />
        </div>
        <label>登录默认首页</label>
        <a-select
          v-model:value="config.rules[role].home"
          :options="homeOptions(role)"
          :disabled="saving"
          style="width: 100%"
          :aria-label="`${label}默认首页`"
        />
      </section>
      <a-button type="primary" :loading="saving" :disabled="!valid || loading" @click="save"
        >保存页面权限</a-button
      >
    </div>
  </section>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { pageAccessApi } from '@/apis/page_access_api'
const roles = { user: '普通用户', ducha: '督查人员', admin: '管理员' }
const config = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const options = (role) =>
  (config.value?.catalog || [])
    .filter((p) => p.roles.includes(role))
    .map((p) => ({ label: p.label, value: p.path }))
const homeOptions = (role) =>
  options(role).filter(
    (p) =>
      config.value.rules[role].pages === null || config.value.rules[role].pages.includes(p.value)
  )
const valid = computed(
  () =>
    config.value &&
    Object.keys(roles).every((role) =>
      homeOptions(role).some((p) => p.value === config.value.rules[role].home)
    )
)
const setPages = (role, pages) => {
  const rule = config.value.rules[role]
  rule.pages = pages
  if (!pages.includes(rule.home)) rule.home = pages[0]
}
const setRestricted = (role, value) => {
  config.value.rules[role].pages = value ? [config.value.rules[role].home] : null
}
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    config.value = await pageAccessApi.manage()
  } catch {
    error.value = '页面配置加载失败，请重试。'
    config.value = null
  } finally {
    loading.value = false
  }
}
const save = async () => {
  if (saving.value || !valid.value) return
  saving.value = true
  error.value = ''
  try {
    const saved = await pageAccessApi.save({
      revision: config.value.revision,
      rules: config.value.rules
    })
    config.value = { ...config.value, ...saved }
    message.success('页面权限已保存，相关角色下次进入页面时生效')
  } catch (e) {
    error.value =
      e.status === 409 ? '配置已被修改，请重新加载后编辑。' : '保存失败，请检查配置后重试。'
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>
<style scoped>
.role-rules {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}
.role-rule {
  border: 1px solid var(--gray-200);
  padding: 16px;
  border-radius: 8px;
}
label {
  display: block;
  margin: 12px 0 6px;
}
</style>
