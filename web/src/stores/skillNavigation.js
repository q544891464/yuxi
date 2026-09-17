import { ref } from 'vue'
import { defineStore } from 'pinia'
import { skillNavigationApi } from '@/apis/skill_navigation_api'

export const useSkillNavigationStore = defineStore('skillNavigation', () => {
  const nodes = ref([])
  const revision = ref(0)
  const loaded = ref(false)
  const error = ref('')
  let pending

  const accept = (config) => {
    nodes.value = config.nodes
    revision.value = config.revision
    loaded.value = true
    error.value = ''
  }
  const load = async (force = false) => {
    if (pending) return pending
    if (loaded.value && !force) return
    pending = skillNavigationApi
      .get()
      .then(accept)
      .catch((err) => {
        error.value = '技能菜单加载失败，请重试'
        throw err
      })
      .finally(() => {
        pending = null
      })
    return pending
  }
  return { nodes, revision, loaded, error, load, accept }
})
