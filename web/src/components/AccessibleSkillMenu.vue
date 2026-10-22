<template>
  <section class="accessible-skill-menu" aria-label="技能菜单">
    <div class="menu-heading" :class="{ 'menu-heading-compact': !showTitle }">
      <span v-if="showTitle">技能</span>
      <button type="button" class="add-skill" :disabled="disabled" @click="$emit('create')">
        添加技能
      </button>
    </div>

    <div v-if="loading || (!navigation.loaded && !menuError)" class="menu-state" role="status">
      正在加载技能...
    </div>
    <div v-else-if="menuError" class="menu-state menu-error" role="alert">
      <span>{{ menuError }}</span>
      <button type="button" @click="loadSkills">重试</button>
    </div>
    <div v-else-if="!entries.length && !listSkills.length" class="menu-state">暂无可用技能</div>
    <div v-else>
      <SkillNavigationTree
        v-if="navigation.configured"
        :nodes="entries"
        :selected-id="selectedEntryId"
        :disabled="disabled"
        @select="$emit('select', $event)"
      />
      <nav class="skill-list" aria-label="可用技能">
        <button
          v-for="skill in listSkills"
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
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { listAccessibleSkills } from '@/apis/skill_api'
import { normalizeAccessibleSkills, resolveNavigationTree } from '@/utils/accessibleSkills'
import { useSkillNavigationStore } from '@/stores/skillNavigation'
import SkillNavigationTree from '@/components/SkillNavigationTree.vue'

defineProps({
  disabled: { type: Boolean, default: false },
  selectedId: { type: String, default: '' },
  selectedEntryId: { type: String, default: '' },
  showTitle: { type: Boolean, default: true }
})
defineEmits(['select', 'create'])
const navigation = useSkillNavigationStore()
const skills = ref([])
const loading = ref(false)
const error = ref('')
const menuError = computed(() => error.value || navigation.error)
const entries = computed(() => resolveNavigationTree(navigation.tree, skills.value))
const listSkills = computed(() =>
  navigation.configured
    ? skills.value.filter((skill) => skill.source_scope === 'personal')
    : skills.value
)
let loadGeneration = 0

/** 配置与可访问列表共同决定菜单，未保存配置沿用原列表。 */
async function loadSkills() {
  const version = ++loadGeneration
  loading.value = true
  error.value = ''
  skills.value = []
  try {
    const [response] = await Promise.all([listAccessibleSkills(), navigation.load()])
    if (version === loadGeneration) skills.value = normalizeAccessibleSkills(response)
  } catch {
    if (version === loadGeneration) error.value = '技能加载失败'
  } finally {
    if (version === loadGeneration) loading.value = false
  }
}
watch(
  () => navigation.loaded,
  (loaded) => {
    if (!loaded) void loadSkills()
  }
)
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
