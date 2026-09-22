<script setup>
defineProps({
  modelValue: { type: Object, required: true },
  directory: { type: Object, required: true }
})
const emit = defineEmits(['update:modelValue'])
const roles = [
  { value: 'user', label: '普通用户' },
  { value: 'ducha', label: '督查人员' },
  { value: 'admin', label: '管理员' },
  { value: 'superadmin', label: '超级管理员' }
]
</script>

<template>
  <div class="scope-fields">
    <a-select
      mode="multiple"
      placeholder="指定人员"
      aria-label="指定人员"
      :value="modelValue.user_uids"
      :options="directory.users.map((u) => ({ value: u.uid, label: u.name }))"
      :filter-option="(input, option) => option.label.includes(input)"
      @update:value="emit('update:modelValue', { ...modelValue, user_uids: $event })"
    />
    <a-select
      mode="multiple"
      placeholder="角色"
      aria-label="角色"
      :value="modelValue.roles"
      :options="roles"
      @update:value="emit('update:modelValue', { ...modelValue, roles: $event })"
    />
    <a-select
      mode="multiple"
      placeholder="部门"
      aria-label="部门"
      :value="modelValue.department_ids"
      :options="directory.departments.map((d) => ({ value: d.id, label: d.name }))"
      @update:value="emit('update:modelValue', { ...modelValue, department_ids: $event })"
    />
  </div>
</template>

<style scoped>
.scope-fields {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
</style>
