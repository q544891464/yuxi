import { ref, watch } from 'vue'
import { useUserStore } from './user'
import { defineStore } from 'pinia'
import { skillNavigationApi } from '@/apis/skill_navigation_api'

export const useSkillNavigationStore = defineStore('skillNavigation', () => {
  const nodes = ref([])
  const revision = ref(0)
  const loaded = ref(false)
  const error = ref('')
  let pending
  let generation = 0
  const userStore = useUserStore()
  watch(
    () => [userStore.userId, userStore.userRole],
    () => {
      generation += 1
      nodes.value = []
      loaded.value = false
      pending = null
    },
    { flush: 'sync' }
  )

  const accept = (config) => {
    nodes.value = config.nodes
    revision.value = config.revision
    loaded.value = true
    error.value = ''
  }
  const load = async (force = false) => {
    if (pending && !force) return pending
    if (loaded.value && !force) return
    if (force) generation += 1
    const requestGeneration = generation
    pending = skillNavigationApi
      .get()
      .then((config) => {
        if (requestGeneration === generation) accept(config)
      })
      .catch((err) => {
        if (requestGeneration === generation) error.value = '技能菜单加载失败，请重试'
        throw err
      })
      .finally(() => {
        if (requestGeneration === generation) pending = null
      })
    return pending
  }
  return { nodes, revision, loaded, error, load, accept }
})
