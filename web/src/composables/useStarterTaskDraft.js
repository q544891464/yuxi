import { computed, ref, watch } from 'vue'

/** 预览只属于打开时的草稿；上下文、能力或输入变化后旧确认失效。 */
export function useStarterTaskDraft({ contextKey, examples, enabled, userInput }) {
  const preview = ref(null)
  const hasDraft = computed(() => Boolean(userInput.value.trim()))
  const dismiss = () => {
    preview.value = null
  }
  watch([contextKey, examples, enabled, userInput], dismiss, { flush: 'sync' })

  /** 只接受当前员工实际展示的示例。 */
  function open(exampleId) {
    if (!enabled.value) return false
    const example = examples.value.find((item) => item.id === exampleId)
    if (!example) return false
    preview.value = { ...example, context: contextKey.value, original: userInput.value }
    return true
  }

  /** 用户确认后仅替换输入，不创建会话或发起运行。 */
  function apply() {
    const pending = preview.value
    if (
      !pending ||
      !enabled.value ||
      pending.context !== contextKey.value ||
      pending.original !== userInput.value ||
      !examples.value.some((item) => item.id === pending.id)
    )
      return false
    userInput.value = pending.prompt
    dismiss()
    return true
  }

  return { preview, hasDraft, open, apply, dismiss }
}
