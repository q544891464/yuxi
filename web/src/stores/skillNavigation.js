import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useUserStore } from './user'
import { skillNavigationApi } from '@/apis/skill_navigation_api'

export const useSkillNavigationStore = defineStore('skillNavigation', () => {
  const tree = ref([])
  const configured = ref(false)
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref('')
  let generation = 0
  let pending = null
  const userStore = useUserStore()

  /** 账户变更或配置保存后，旧响应不能覆盖新的菜单。 */
  const invalidate = () => {
    generation += 1
    tree.value = []
    configured.value = false
    loaded.value = false
    loading.value = false
    error.value = ''
    pending = null
  }
  watch(() => [userStore.userId, userStore.userRole], invalidate, { flush: 'sync' })

  /** 合并同一身份的菜单读取，失败保持可重试状态。 */
  const load = ({ force = false } = {}) => {
    if (pending) return pending
    if (loaded.value && !force) return Promise.resolve()
    const requestGeneration = ++generation
    loading.value = true
    error.value = ''
    pending = skillNavigationApi
      .get()
      .then((config) => {
        if (requestGeneration !== generation) return
        tree.value = config.tree
        configured.value = config.configured
        loaded.value = true
      })
      .catch((err) => {
        if (requestGeneration === generation) error.value = '技能菜单加载失败，请重试'
        throw err
      })
      .finally(() => {
        if (requestGeneration !== generation) return
        pending = null
        loading.value = false
      })
    return pending
  }
  return { tree, configured, loaded, loading, error, load, invalidate }
})
