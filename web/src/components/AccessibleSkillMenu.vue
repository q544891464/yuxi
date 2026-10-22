<template>
  <section class="accessible-skill-menu" aria-label="技能菜单">
    <div class="menu-heading" :class="{ 'menu-heading-compact': !showTitle }">
      <span v-if="showTitle">技能</span>
      <button type="button" class="add-skill" :disabled="disabled" @click="$emit('create')">
        添加技能
      </button>
    </div>

    <div v-if="loading" class="menu-state" role="status">正在加载技能...</div>
    <div v-else-if="error" class="menu-state menu-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="loadSkills">重试</button>
    </div>
    <div v-else-if="!skills.length" class="menu-state">暂无可用技能</div>
    <nav v-else class="skill-list" aria-label="可用技能">
      <button
        v-for="skill in skills"
        :key="skill.slug"
        type="button"
        class="skill-entry"
        :class="{ selected: selectedId === skill.slug }"
        :title="skill.description || skill.name || skill.slug"
        :disabled="disabled"
        @click="$emit('select', skill)"
      >
        <span class="skill-name">{{ skill.display_name || skill.name || skill.slug }}</span>
      </button>
    </nav>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { listAccessibleSkills } from '@/apis/skill_api'
import { normalizeAccessibleSkills } from '@/utils/accessibleSkills'

defineProps({
  disabled: { type: Boolean, default: false },
  selectedId: { type: String, default: '' },
  showTitle: { type: Boolean, default: true }
})

defineEmits(['select', 'create'])

const skills = ref([])
const loading = ref(false)
const error = ref('')

/** 读取后端已按当前用户权限过滤的可用技能。 */
async function loadSkills() {
  loading.value = true
  error.value = ''
  try {
    const response = await listAccessibleSkills()
    skills.value = normalizeAccessibleSkills(response)
  } catch {
    skills.value = []
    error.value = '技能加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadSkills)
</script>

<style lang="less" scoped>
.accessible-skill-menu {
  margin-top: 14px;
}
.menu-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  color: var(--gray-600);
  font-size: 14px;
  font-weight: 600;
}
.menu-heading-compact {
  justify-content: flex-start;
  padding-left: 8px;
}
.add-skill,
.menu-error button {
  padding: 2px 4px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--main-color);
  cursor: pointer;
  font-size: 12px;
}
.add-skill:disabled,
.skill-entry:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.skill-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.skill-entry {
  display: flex;
  align-items: center;
  min-height: 30px;
  padding: 0 8px 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--gray-800);
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  &:hover,
  &.selected {
    background: var(--gray-50);
    color: var(--main-color);
  }
  &:focus-visible {
    outline: 2px solid var(--main-300);
    outline-offset: -2px;
  }
}
.skill-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.menu-state {
  padding: 8px;
  color: var(--gray-500);
  font-size: 12px;
}
.menu-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--color-error-700);
}
</style>
